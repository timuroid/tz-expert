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

from models import AnalyzeRequest, AnalyzeResponse, ErrorOut, Finding, TokenStat  ### 🔧
from llm import ask_llm, LLMError
import utils                                          # опционально

# ---- Грузим YAML ----
with open("errors.yaml", encoding="utf-8") as f:
    RULES = {r["code"]: r for r in yaml.safe_load(f)}

app = FastAPI(title="TZ-Expert LLM API", version="0.3")

# ---------- PROMPT-ГЕНЕРАТОРЫ ----------
def triage_prompt(html: str, detector: str) -> List[dict]:
    """Промпт → {"exists": true/false}"""
    return [
        {"role": "system",
         "content": 'Отвечай ТОЛЬКО JSON вида {"exists":true/false}.'},
        {"role": "user", "content": f"<document>\n{html}\n</document>"},
        {"role": "user", "content": detector}
    ]

def deep_prompt(html: str, rule: dict) -> List[dict]:
    """
    Просим строгий JSON:
    {
      "code":"E05","title":"…","kind":"Invalid",
      "findings":[
        {"paragraph":"id","quote":"цитата","advice":"…"}
      ]
    }
    """
    schema = (
        '{"code":"%(code)s","title":"%(title)s","kind":"%(kind)s",'
        '"findings":[{"paragraph":"","quote":"","advice":""}]}' % rule
    )
    return [
        {"role": "system",
         "content": "Отвечай ТОЛЬКО JSON по образцу: " + schema},
        {"role": "user", "content": f"<document>\n{html}\n</document>"},
        {"role": "user", "content": rule["detector"]}
    ]

# ---------- ЭНД-ПОИНТЫ ----------
@app.get("/errors")
async def list_rules():
    """Справочник правил (как есть)."""
    return JSONResponse(RULES)

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    codes = req.codes or list(RULES.keys())

    # --- счётчик токенов -------------------------------------------------  ### 🔧
    tokens = {"prompt": 0, "completion": 0}

    # TRIAGE
    async def triage(code: str):
        rule = RULES[code]
        try:
            raw, usage = await ask_llm(triage_prompt(req.html, rule["detector"]))  ### 🔧
            tokens["prompt"]     += usage.get("prompt_tokens", 0)                  ### 🔧
            tokens["completion"] += usage.get("completion_tokens", 0) 
            return code, json.loads(raw)["exists"]
        except Exception:
            return code, False

    triage_pairs = await asyncio.gather(*[triage(c) for c in codes])
    positives = [c for c, ok in triage_pairs if ok]

    # DEEP
    async def deep(code: str):
        rule = RULES[code]
        try:
            raw, usage = await ask_llm(deep_prompt(req.html, rule))     ### 🔧
            tokens["prompt"]     += usage.get("prompt_tokens", 0)       ### 🔧
            tokens["completion"] += usage.get("completion_tokens", 0)   ### 🔧
            data = json.loads(raw)                       # dict от LLM
            # маппинг → Pydantic
            findings = [Finding(**f) for f in data["findings"]]
            return ErrorOut(code=rule["code"],
                            title=rule["title"],
                            kind=rule["kind"],
                            findings=findings)
        except (LLMError, json.JSONDecodeError) as exc:
            # бэкап-вариант: выводим ошибку внутрь advice
            return ErrorOut(code=rule["code"], title=rule["title"],
                            kind=rule["kind"],
                            findings=[Finding(paragraph="?",
                                              quote="-",
                                              advice=str(exc))])

    detailed = await asyncio.gather(*[deep(c) for c in positives])

     # финальный расчёт ----------------------------------------------------  ### 🔧
    tokens["total"] = tokens["prompt"] + tokens["completion"]

    logging.info("tokens_in=%s", utils.count_tokens(req.html) * len(codes))
    return AnalyzeResponse(errors=detailed, tokens=TokenStat(**tokens))
