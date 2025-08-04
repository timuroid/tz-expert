"""
main.py

FastAPI-приложение 
"""

from fastapi import FastAPI
from tz_expert.app.routers import router

app = FastAPI(
    title="TZ-Expert LLM API",
    version="0.5",
    description="Сервис структурированного анализа Markdown-документов (structure-guided reasoning).",
    openapi_tags=[
        {"name": "Structured Analysis", "description": "Structure-guided group reasoning"}
    ]
)

app.include_router(router)
