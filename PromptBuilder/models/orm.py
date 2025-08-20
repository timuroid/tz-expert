"""
models/orm.py
ORM-модели под текущую БД:
- error_group_groups (GG)
- error_groups (группа, FK -> GG)
- errors (ошибка, FK -> группа)
"""
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from PromptBuilder.core.db import Base

class ErrorGroupGroup(Base):
    __tablename__ = "error_group_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    groups = relationship("ErrorGroup", back_populates="ggroup")

class ErrorGroup(Base):
    __tablename__ = "error_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    code = Column(Text, nullable=True)  # код группы, например "G7"
    group_description = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    gg_id = Column(Integer, ForeignKey("error_group_groups.id"), nullable=True)

    errors = relationship("Error", back_populates="group", cascade="all,delete-orphan")
    ggroup = relationship("ErrorGroupGroup", back_populates="groups")

    __table_args__ = (
        Index("ix_error_groups_gg_id", "gg_id"),
        Index("ix_error_groups_not_deleted", "is_deleted"),
    )

class Error(Base):
    __tablename__ = "errors"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    detector = Column(Text, nullable=False)
    group_id = Column(Integer, ForeignKey("error_groups.id"), nullable=False)

    group = relationship("ErrorGroup", back_populates="errors")
