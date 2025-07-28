# tz_expert/models/orm.py
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from tz_expert.db import Base

class ErrorGroup(Base):
    __tablename__ = "error_groups"

    id                = Column(Integer, primary_key=True, index=True)
    name              = Column(String, nullable=False)
    group_description = Column(Text, nullable=True)
    is_deleted        = Column(Boolean, default=False)

    # Связь 1→M c таблицей ошибок
    errors = relationship("Error", back_populates="group")

class Error(Base):
    __tablename__ = "errors"

    id          = Column(Integer, primary_key=True, index=True)
    code        = Column(String, unique=True, nullable=False)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    detector    = Column(Text, nullable=False)
    group_id    = Column(Integer, ForeignKey("error_groups.id"), nullable=False)

    # Ссылка обратно на группу
    group       = relationship("ErrorGroup", back_populates="errors")
