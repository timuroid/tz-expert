"""
app.py
-------
FastAPI-приложение с логикой:
 1. TRIAGE  — да/нет для каждого кода
 2. DEEP    — подробности только для «да»
"""

import json, yaml, asyncio, logging
from typing import List
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from models import AnalyzeRequest, AnalyzeResponse, AnalyzeOut, Finding, TokenStat  
from llm import (ask_llm, LLMError, TRIAGE_SYSTEM, DEEP_SYSTEM,TRIAGE_SCHEMA, DEEP_SCHEMA)
import utils                                          # опционально

# ---- Грузим YAML ----
with open("errors.yaml", encoding="utf-8") as f:
    RULES = {r["code"]: r for r in yaml.safe_load(f)}

app = FastAPI(title="TZ-Expert LLM API", version="0.3")

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

# ---------- ЭНД-ПОИНТЫ ----------
@app.get("/errors")
async def list_rules():
    """Справочник правил (как есть)."""
    return JSONResponse(RULES)    # добавить возможность получания информации по конкретной ошибке исходя из её кода 

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    codes = req.codes or list(RULES.keys())

    # --- счётчик токенов -------------------------------------------------  
    tokens = {"prompt": 0, "completion": 0}

    # TRIAGE
    async def triage(code: str):
        rule = RULES[code]
        try:
            obj, usage = await ask_llm(triage_prompt(req.html, rule),
                                       TRIAGE_SCHEMA)  
            tokens["prompt"]     += usage.get("prompt_tokens", 0)                  
            tokens["completion"] += usage.get("completion_tokens", 0) 
            return code, obj["exists"]
        except Exception as exc:
            logging.error("LLM failure on %s: %s", code, exc)
            return code, False

    triage_pairs = await asyncio.gather(*[triage(c) for c in codes])
    positives = [c for c, ok in triage_pairs if ok]

    # DEEP
    async def deep(code: str):
        rule = RULES[code]
        try:
            obj, usage = await ask_llm(deep_prompt(req.html, rule),
                                       DEEP_SCHEMA)     
            tokens["prompt"]     += usage.get("prompt_tokens", 0)       
            tokens["completion"] += usage.get("completion_tokens", 0)   
            # маппинг → Pydantic
            findings = [Finding(**f) for f in obj["findings"]]
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
