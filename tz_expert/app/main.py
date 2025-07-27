"""
main.py

FastAPI-приложение 
"""

from fastapi import FastAPI
from .routers import router



app = FastAPI(
    title="TZ-Expert LLM API",
    version="0.4",
    description="Сервис проверки технических заданий: триаж и детальный анализ ошибок по списку правил.",
    openapi_tags=[
        {"name": "Rules", "description": "Работа со справочником правил"},
        {"name": "Analysis", "description": "Проверка и анализ документов"}
    ]
)

app.include_router(router)