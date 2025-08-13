"""
Тарифы (₽) и модели Яндекс Foundation Models.
Источник: оф. документация YC (обновлено 12.08.2025).
См. таблицы "Цены для региона Россия" и перечень моделей/URI. 
"""

from __future__ import annotations
from typing import Dict

# ---- Рублёвые цены за 1000 токенов (вкл. НДС) -------------------------------
# Таблица из "Стоимость использования моделей в синхронном и асинхронном режиме".
# Qwen3 235B — только sync (по таблице у async стоит "—").
PRICING_RUB_PER_1K: Dict[str, Dict[str, float]] = {
    "sync": {
        "yandexgpt-lite": 0.20,
        "yandexgpt": 1.20,           # Pro
        "datasphere-finetuned": 1.20,
        "llama-lite": 0.20,          # Llama 8B
        "llama": 1.20,               # Llama 70B
        "qwen3-235b": 0.50,          # со скидкой 50% по оф. странице
        "gpt-oss-120b": 0.30,
        "gpt-oss-20b": 0.10,
    },
    "async": {
        "yandexgpt-lite": 0.10,
        "yandexgpt": 0.60,
        "datasphere-finetuned": 0.60,
        "llama-lite": 0.10,
        "llama": 0.60,
        # для qwen3-235b и gpt-oss-* в таблице async нет → не поддерживаем
    },
}

# ---- Вспомогательная нормализация ярлыков модели из URI ---------------------
# Примеры URI (см. docs):
#  - gpt://<folder>/yandexgpt-lite[/latest]
#  - gpt://<folder>/yandexgpt
#  - gpt://<folder>/llama-lite
#  - gpt://<folder>/llama
#  - gpt://<folder>/gpt-oss-120b
#  - gpt://<folder>/gpt-oss-20b
#  - gpt://<folder>/qwen3-235b-a22b-fp8[/latest]  → сводим к 'qwen3-235b'
def normalize_model_label(model_uri: str) -> str:
    lower = model_uri.lower()
    # порядок проверок важен
    if "/yandexgpt-lite" in lower:
        return "yandexgpt-lite"
    if "/yandexgpt-32k" in lower or "/yandexgpt" in lower:
        return "yandexgpt"
    if "/llama-lite" in lower:
        return "llama-lite"
    if "/llama" in lower:
        return "llama"
    if "/gpt-oss-120b" in lower:
        return "gpt-oss-120b"
    if "/gpt-oss-20b" in lower:
        return "gpt-oss-20b"
    if "/qwen3-235b" in lower:
        return "qwen3-235b"
    # базовый дефолт — Pro
    return "yandexgpt"

def price_per_1k_rub(model_label: str, mode: str) -> float:
    mode_tbl = PRICING_RUB_PER_1K.get(mode, PRICING_RUB_PER_1K["sync"])
    # если конкретной модели нет в режиме — падаем на цену Pro sync
    return float(mode_tbl.get(model_label, PRICING_RUB_PER_1K["sync"]["yandexgpt"]))

def price_per_1m_rub(model_label: str, mode: str) -> float:
    # 1М = 1000 * (цена за 1000)
    return round(price_per_1k_rub(model_label, mode) * 1000.0, 6)


# ---- (Опционально) перечень моделей для справки, которые можно использовать -
# Синхронный/асинхронный режимы:
#  - yandexgpt-lite, yandexgpt, llama-lite, llama, gpt-oss-20b, gpt-oss-120b
# Только OpenAI API (и только sync в прайс-таблице):
#  - qwen3-235b-a22b-fp8 (нормализуем как 'qwen3-235b')
SUPPORTED_MODELS_HINT = [
    {"label": "yandexgpt-lite", "uri": "gpt://<folder>/yandexgpt-lite[/latest]", "modes": ["sync","async"]},
    {"label": "yandexgpt",      "uri": "gpt://<folder>/yandexgpt[/latest]",      "modes": ["sync","async"]},
    {"label": "llama-lite",     "uri": "gpt://<folder>/llama-lite[/latest]",     "modes": ["sync","async"]},
    {"label": "llama",          "uri": "gpt://<folder>/llama[/latest]",          "modes": ["sync","async"]},
    {"label": "gpt-oss-20b",    "uri": "gpt://<folder>/gpt-oss-20b",             "modes": ["sync"]},
    {"label": "gpt-oss-120b",   "uri": "gpt://<folder>/gpt-oss-120b",            "modes": ["sync"]},
    {"label": "qwen3-235b",     "uri": "gpt://<folder>/qwen3-235b-a22b-fp8[/latest]", "modes": ["sync"]},
]
