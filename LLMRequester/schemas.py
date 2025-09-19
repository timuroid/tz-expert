"""Pydantic DTOs for LLMRequester."""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class RunRequest(BaseModel):
    messages: List[ChatMessage]
    schema_: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    model: Optional[str] = None
    mode: Optional[Literal["sync", "async"]] = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Cost(BaseModel):
    currency: Literal["RUB"] = "RUB"
    model_label: str
    mode: Literal["sync", "async"]
    price_per_1m: float
    total_rub: float


class RunResponse(BaseModel):
    """Provider reply: either JSON (if schema enforced) or raw text."""

    result: Union[Dict[str, Any], str]
    usage: Usage
    cost: Cost
    model_uri: str
    attempts: int
