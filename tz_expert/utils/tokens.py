# tokens.py
import tiktoken
from tz_expert.settings import settings  # ✅ прямой импорт, а не алиас

_enc_cache: dict[str, tiktoken.Encoding] = {}

def count_tokens(text: str) -> int:
    model = settings.llm_model
    enc = _enc_cache.get(model)
    if enc is None:
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        _enc_cache[model] = enc
    return len(enc.encode(text))