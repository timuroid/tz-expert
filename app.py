"""
app.py
-------
FastAPI-приложение с логикой:
 1. TRIAGE  — да/нет для каждого кода
 2. DEEP    — подробности только для «да»
"""

import json, yaml, asyncio, logging
from typing import List, Dict
from pathlib import Path
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse

from models import AnalyzeRequest, AnalyzeResponse, AnalyzeOut, Finding, TokenStat  
from llm import ask_llm, LLMError, TRIAGE_SYSTEM, TRIAGE_GROUP_SYSTEM, DEEP_SYSTEM
import utils                                          # опционально

# ---- Грузим YAML ----
with open("errors.yaml", encoding="utf-8") as f:
    RULES = {r["code"]: r for r in yaml.safe_load(f)}

# ----- Загрузка групп из groups.yaml -----
# Читаем весь файл, декодируем в словарь Python
groups_data = yaml.safe_load(Path("groups.yaml").read_text(encoding="utf-8"))
# Создаём словарь для быстрого доступа по ID группы
GROUPS_MAP = {g["id"]: g for g in groups_data["groups"]}
# Список всех ID — для дефолтного triage
DEFAULT_GROUPS = [g["id"] for g in groups_data["groups"]]

app = FastAPI(
    title="TZ-Expert LLM API",
    version="0.4",
    description="Сервис проверки технических заданий: триаж и детальный анализ ошибок по списку правил.",
    openapi_tags=[
        {"name": "Rules", "description": "Работа со справочником правил"},
        {"name": "Analysis", "description": "Проверка и анализ документов"}
    ]
)

# ---------- PROMPT-ГЕНЕРАТОРЫ ----------
def triage_prompt(html: str, rule: dict) -> List[dict]:
    """Промпт → {"exists": true/false}"""
    return [
        {"role": "system","content": TRIAGE_SYSTEM},
        {"role": "user", "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user", "content": f"'Код ошибки' : '{rule['code']}',\n'Название ошибки' : '{rule['title']}',\n'Описание ошибки' : '{rule['description']}',\n'Способ обнаружения ошибки' : '{rule['detector']}'"}
    ]

def deep_prompt(html: str, rule: dict) -> List[dict]:
    return [
        {"role": "system", "content": DEEP_SYSTEM},
        {"role": "user", "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user", "content": f"'Код ошибки' : '{rule['code']}',\n'Название ошибки' : '{rule['title']}',\n'Описание ошибки' : '{rule['description']}',\n'Способ обнаружения ошибки' : '{rule['detector']}'"}
    ]

def triage_group_prompt(html: str, group_def: dict) -> List[dict]:
    # 1) Основной system-prompt
    # 2) Добавляем внутри него custom-system для данной группы
    group_prompt = group_def["system_prompt"]

    # 3) Собираем тело: для каждого code в группе выгружаем свойства из RULES
    lines: List[str] = []
    for code in group_def["codes"]:
        r = RULES[code]
        # Внутри LLM получает сразу весь контекст группы, снижая дубли и противоречия
        lines.append(
            f"Код: {r['code']}\n"
            f"Название: {r['title']}\n"
            f"Описание: {r['description']}\n"
            f"Детектор: {r['detector']}"
        )
    body = "\n\n".join(lines)

    return [
        {"role": "system", "content": TRIAGE_GROUP_SYSTEM},
        {"role": "user",   "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user",   "content": group_prompt + body + "\n\n Верни ровно JSON"},
    ]

# ---------- ЭНД-ПОИНТЫ ----------
@app.get("/errors",
    summary="Получить все правила ошибок",
    description=(
        "Возвращает полный словарь правил проверки ТЗ, загруженных из errors.yaml. \n"
        "Каждое правило содержит: код, название, описание, детектор способа поиска ошибки."
    ),
    response_description="Словарь правил (ключ — код ошибки, значение — детали правила)",
    response_model=Dict[str, dict],
    tags=["Rules"]
)
async def list_rules():
    """
    Получить справочник всех доступных правил проверки ТЗ.
    """
    return JSONResponse(RULES)    # добавить возможность получания информации по конкретной ошибке исходя из её кода 

@app.post("/analyze",
    summary="Анализ документа на наличие ошибок",
    description=(
        "Принимает HTML-документ и по коду или по группам выполняет:\n"
        "1) Групповой и одиночный triage (быстрая проверка существования ошибки)\n"
        "2) Детальный DEEP-анализ для найденных ошибок\n"
        "Возвращает список ошибок с рекомендациями и статистику токенов."
    ),
    response_description="Результат анализа: найденные ошибки и статистика использования токенов",
    response_model=AnalyzeResponse,
    tags=["Analysis"]
)
async def analyze(req: AnalyzeRequest = Body(
        ...,
        example={
            "html": "<h1>Пример ТЗ</h1><p>Контент...</p>",
            "codes": ["E01", "E02"],
            "groups": ["G01", "G02"],
            "model":"gpt-4.1-mini-2025-04-14"
        }
    )
):
    """
    Анализирует переданный HTML на наличие ошибок по заданным кодам или группам.

    :param req.html: строка с HTML содержимым документа
    :param req.codes: список кодов ошибок для одиночной проверки
    :param req.groups: список групп ошибок для группового triage
    :return: объект AnalyzeResponse с деталями найденных ошибок и статистикой токенов
    """
    requested_model = req.model

    # 1) Подготовка списков triage
    codes  = req.codes or []
    groups = req.groups or []
    if not codes and not groups:
        groups = DEFAULT_GROUPS  # используем все группы по умолчанию

    # --- счётчик токенов -------------------------------------------------  
    tokens = {"prompt": 0, "completion": 0}

    triage_pairs: List[tuple[str, bool]] = []

    # --- Групповой TRIAGE ---
    async def triage_group(grp_id: str) -> List[tuple[str, bool]]:
        # Получаем определение группы по ID из GROUPS_MAP
        group_def = GROUPS_MAP[grp_id]
        # Вызов LLM с batched prompt
        obj, usage = await ask_llm(
            triage_group_prompt(req.html, group_def),
            model=requested_model
        )
        # Накопление токенов
        tokens["prompt"]     += usage.get("prompt_tokens", 0)
        tokens["completion"] += usage.get("completion_tokens", 0)
        # Возвращаем list of tuples (code, exists)
        return [(res["code"], res["exists"]) for res in obj["results"]]

    if groups:
        grp_results = await asyncio.gather(*(triage_group(g) for g in groups))
        # Выпрямляем вложенные списки
        triage_pairs += [p for sub in grp_results for p in sub]

    # --- Одиночный TRIAGE ---
    async def triage_single(code: str) -> tuple[str, bool]:
        rule = RULES[code]
        try:
            obj, usage = await ask_llm(triage_prompt(
                req.html, rule),
                model=requested_model
                )  
            tokens["prompt"]     += usage.get("prompt_tokens", 0)                  
            tokens["completion"] += usage.get("completion_tokens", 0) 
            return code, obj.get("exists", False)
        except Exception as exc:
            logging.error("LLM failure on %s: %s", code, exc)
            return code, False

    if codes:
        single_results = await asyncio.gather(*(triage_single(c) for c in codes))
        triage_pairs += single_results

    
    positives = [c for c, ok in triage_pairs if ok]

    # DEEP
    async def deep(code: str):
        rule = RULES[code]
        try:
            obj, usage = await ask_llm(deep_prompt(
                req.html, rule),
                model=requested_model
                )     
            tokens["prompt"]     += usage.get("prompt_tokens", 0)       
            tokens["completion"] += usage.get("completion_tokens", 0)   
            # маппинг → Pydantic
            findings = [Finding(**f) for f in obj.get("findings", [])]
            return AnalyzeOut(code=obj["code"],
                            title=obj["title"],
                            findings=findings)
        except (LLMError, json.JSONDecodeError) as exc:
            logging.error("LLM deep error %s: %s", code, exc)
            # бэкап-вариант: выводим ошибку внутрь advice
            return AnalyzeOut(code=rule["code"], title=rule["title"],
                            kind=rule["kind"],
                            findings=[Finding(paragraph="?",
                                              quote="-",
                                              advice=str(exc))])

    detailed = await asyncio.gather(*[deep(c) for c in positives])

     # финальный расчёт ----------------------------------------------------  
    tokens["total"] = tokens["prompt"] + tokens["completion"]

    logging.info("tokens_in=%s", utils.count_tokens(req.html) * len(codes))
    return AnalyzeResponse(errors=detailed, tokens=TokenStat(**tokens))
