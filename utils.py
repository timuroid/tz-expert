# utils.py
import tiktoken, settings as _s

_enc_cache: dict[str, tiktoken.Encoding] = {}

def count_tokens(text: str) -> int:
    """
    Возвращает количество токенов.
    Если модель не распознана tiktoken, используем универсальный
    энкодер cl100k_base, чтобы не падать с KeyError.
    """
    model = _s.settings.openai_model          # например gpt-4.1-2025-04-14
    if model not in _enc_cache:
        try:
            _enc_cache[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            # fallback: максимально близкий универсальный энкодер
            _enc_cache[model] = tiktoken.get_encoding("cl100k_base")
    return len(_enc_cache[model].encode(text))
