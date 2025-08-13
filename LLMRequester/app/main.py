"""
Запуск: uvicorn LLMRequester.app.main:app --reload --port 8020
"""
from fastapi import FastAPI
from .routers import router

app = FastAPI(
    title="LLM Requester API",
    version="1.0.0",
    description="Мини-сервис исполнения LLM-запросов (OpenAI-compatible, Yandex Cloud).",
)

app.include_router(router)
