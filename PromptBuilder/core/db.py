"""SQLAlchemy: инициализация `engine`, `SessionLocal` и базового класса моделей.

Использует строку подключения из `PB_DATABASE_URL`.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from PromptBuilder.core.settings import settings

engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    """Базовый declarative‑класс для ORM‑моделей SQLAlchemy."""
    pass

