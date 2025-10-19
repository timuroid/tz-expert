"""`nВспомогательные функции расчёта стоимости для LLMRequester.`n`nМодель ценообразования упрощена и задаётся тарифом на 1К токенов для`nкаждого ярлыка модели. Стоимость ответа считается пропорционально общему`nчислу токенов, возвращаемому провайдером.`n"""
from __future__ import annotations

from typing import Dict

# Price per 1K tokens in RUB per model (rough public data)
PRICING_RUB_PER_1K: Dict[str, float] = {
    "yandexgpt-lite": 0.20,
    "yandexgpt": 1.20,
    "datasphere-finetuned": 1.20,
    "llama-lite": 0.20,
    "llama": 1.20,
    "qwen3-235b": 0.50,
    "gpt-oss-120b": 0.30,
    "gpt-oss-20b": 0.10,
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
    """
    Преобразовать полный URI модели к ярлыку для прайсинга.
    Ищет известные префиксы в строке URI и возвращает соответствующий ярлык.
    Если ничего не найдено — используется дефолтный "yandexgpt"   
    """
    lower = model_uri.lower()
    for prefix, label in MODEL_PREFIXES.items():
        if prefix in lower:
            return label
    # default to the main YandexGPT pro model
    return "yandexgpt"


def price_per_1k_rub(model_label: str) -> float:
    """Цена за 1К токенов в рублях для указанного ярлыка модели."""
    return float(PRICING_RUB_PER_1K.get(model_label, PRICING_RUB_PER_1K["yandexgpt"]))


def price_per_1m_rub(model_label: str) -> float:
    """Цена за 1М токенов в рублях для указанного ярлыка модели."""
    return round(price_per_1k_rub(model_label) * 1000.0, 6)


SUPPORTED_MODELS_HINT = [
    {"label": "yandexgpt-lite", "uri": "gpt://<folder>/yandexgpt-lite[/latest]"},
    {"label": "yandexgpt", "uri": "gpt://<folder>/yandexgpt[/latest]"},
    {"label": "llama-lite", "uri": "gpt://<folder>/llama-lite[/latest]"},
    {"label": "llama", "uri": "gpt://<folder>/llama[/latest]"},
    {"label": "gpt-oss-20b", "uri": "gpt://<folder>/gpt-oss-20b"},
    {"label": "gpt-oss-120b", "uri": "gpt://<folder>/gpt-oss-120b"},
    {"label": "qwen3-235b", "uri": "gpt://<folder>/qwen3-235b-a22b-fp8[/latest]"},
]

