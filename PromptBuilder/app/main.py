"""
app/main.py
Запуск: uvicorn PromptBuilder.app.main:app --reload --port 8010
"""
from fastapi import FastAPI
from .routers import router

app = FastAPI(
    title="PromptBuilder API",
    version="1.0.0",
    description="Сервис сборки LLM-messages (markdown + gg_id → items).",
)

app.include_router(router)
