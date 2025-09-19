"""Pricing utilities for LLMRequester."""
from __future__ import annotations

from typing import Dict

# Price per 1K tokens in RUB for supported models/modes (rough public data)
PRICING_RUB_PER_1K: Dict[str, Dict[str, float]] = {
    "sync": {
        "yandexgpt-lite": 0.20,
        "yandexgpt": 1.20,
        "datasphere-finetuned": 1.20,
        "llama-lite": 0.20,
        "llama": 1.20,
        "qwen3-235b": 0.50,
        "gpt-oss-120b": 0.30,
        "gpt-oss-20b": 0.10,
    },
    "async": {
        "yandexgpt-lite": 0.10,
        "yandexgpt": 0.60,
        "datasphere-finetuned": 0.60,
        "llama-lite": 0.10,
        "llama": 0.60,
        # qwen3-235b and gpt-oss models are not yet exposed in async mode
    },
}

# Known prefixes in model URIs -> pricing labels
MODEL_PREFIXES = {
    "/yandexgpt-lite": "yandexgpt-lite",
    "/yandexgpt-32k": "yandexgpt",
    "/yandexgpt": "yandexgpt",
    "/llama-lite": "llama-lite",
    "/llama": "llama",
    "/gpt-oss-120b": "gpt-oss-120b",
    "/gpt-oss-20b": "gpt-oss-20b",
    "/qwen3-235b": "qwen3-235b",
}


def normalize_model_label(model_uri: str) -> str:
    """Map full model URI to a pricing label."""
    lower = model_uri.lower()
    for prefix, label in MODEL_PREFIXES.items():
        if prefix in lower:
            return label
    # default to the main YandexGPT pro model
    return "yandexgpt"


def price_per_1k_rub(model_label: str, mode: str) -> float:
    table = PRICING_RUB_PER_1K.get(mode, PRICING_RUB_PER_1K["sync"])
    return float(table.get(model_label, PRICING_RUB_PER_1K["sync"]["yandexgpt"]))


def price_per_1m_rub(model_label: str, mode: str) -> float:
    return round(price_per_1k_rub(model_label, mode) * 1000.0, 6)


SUPPORTED_MODELS_HINT = [
    {"label": "yandexgpt-lite", "uri": "gpt://<folder>/yandexgpt-lite[/latest]", "modes": ["sync", "async"]},
    {"label": "yandexgpt", "uri": "gpt://<folder>/yandexgpt[/latest]", "modes": ["sync", "async"]},
    {"label": "llama-lite", "uri": "gpt://<folder>/llama-lite[/latest]", "modes": ["sync", "async"]},
    {"label": "llama", "uri": "gpt://<folder>/llama[/latest]", "modes": ["sync", "async"]},
    {"label": "gpt-oss-20b", "uri": "gpt://<folder>/gpt-oss-20b", "modes": ["sync"]},
    {"label": "gpt-oss-120b", "uri": "gpt://<folder>/gpt-oss-120b", "modes": ["sync"]},
    {"label": "qwen3-235b", "uri": "gpt://<folder>/qwen3-235b-a22b-fp8[/latest]", "modes": ["sync"]},
]
