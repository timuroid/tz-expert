# tz_expert/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# 1) URL вашей БД
DATABASE_URL = "postgresql://hrrjskze:FNhRJt_eapnjJ4BnzAz9@94.241.142.172:8083/llm"

# 2) Двигатель и сессии SQLAlchemy
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# 3) Общий базовый класс для ORM-моделей
class Base(DeclarativeBase):
    pass
