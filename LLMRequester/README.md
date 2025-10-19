LLMRequester — сервис вызова LLM (Yandex Cloud, OpenAI‑совместимый)

Назначение
- Тонкая HTTP‑обёртка над OpenAI‑совместимым API Yandex Cloud: принимает сообщения (messages), опциональную JSON‑схему (schema) и модель (model), возвращает результат (текст или JSON), usage и ориентировочную стоимость.

Быстрый старт
- Запуск локально: `uvicorn LLMRequester.app.main:app --reload --port 8020`
- Эндпоинт: `POST /v1/structured/run`

Формат запроса (RunRequest)
- `messages: ChatMessage[]` — список сообщений (обычно минимум 2: system + user)
- `schema: object|null` — опциональная JSON‑схема для принудительного JSON‑вывода (response_format=json_schema)
- `model: string|null` — короткое имя или полный `gpt://<folder>/<model>[/latest]`. Если не задано — берётся `DEFAULT_MODEL` из настроек

Формат ответа (RunResponse)
- `result: object | array | string` — при схеме это JSON (dict/list), иначе — сырая строка
- `usage: { prompt_tokens, completion_tokens, total_tokens }`
- `cost: { currency: "RUB", model_label, price_per_1m, total_rub }`
- `model_uri: string` — фактический URI модели
- `attempts: number` — общее число попыток (ретраи по провайдеру/JSON)

Настройки (LLMRequester/core/settings.py)
- Источники .env (по приоритету): `LLMRequester/llmrequester.env` → `LLMRequester/.env` → `./.env`
- Основные переменные:
  - `YC_API_KEY`, `YC_FOLDER_ID`, `YC_BASE_URL`
  - `MAX_CONCURRENT` — семафор для конкурентности (по умолчанию 10)
  - `HTTP_TIMEOUT` — таймаут HTTP‑клиента (по умолчанию 600 сек)
  - `MAX_RETRY_PROVIDER`, `MAX_RETRY_JSON` — политика повторов
  - `DEFAULT_MODEL` — модель по умолчанию (хвост URI)
  - `LOG_LEVEL`, `REQUEST_LOG`, `REQUEST_ID_HEADER` — параметры логирования

Логирование
- Базовая настройка через `logging.basicConfig` в `app/main.py` (уровень — `LOG_LEVEL`).
- Middleware логирует начало/окончание запроса, статус и длительность. В заголовках ответа возвращает `X-Request-ID`.
- В роутере и клиенте используются `INFO/WARNING/ERROR/DEBUG` логи для ключевых событий.

Обработка ошибок (структурированные LLMError)
- Клиент `services/llm_client.py` классифицирует ошибки провайдера и бросает `LLMError(message, status_code, code, provider_status, attempts, model_uri)`
  - `rate_limited` → 429
  - `timeout` → 504
  - `connection_error` → 502
  - `unauthorized` → 401
  - `forbidden` → 403
  - `bad_request` → 400
  - `upstream_error` → 502
  - `provider_error` (прочее) → 422
  - `json_parse_failed` (после ретраев) → 422
- Роутер маппит `LLMError` в HTTP‑ответ с `detail = { code, message, attempts, model_uri, provider_status? }`

Повторы (retry)
- По транзиентным ошибкам провайдера: экспоненциальная задержка, число попыток — `MAX_RETRY_PROVIDER`
- По ошибкам JSON‑парсинга: добавляется короткая подсказка к сообщениям и повтор — `MAX_RETRY_JSON`

Расчёт стоимости (services/pricing.py)
- Упрощённая таблица цен за 1К токенов по ярлыкам моделей
- Нормализация `model_uri` → `model_label`, далее расчёт `price_per_1k/1m` и `total_rub`

Структура кода
- `app/` — инициализация FastAPI, middleware, роуты
- `core/` — настройки через pydantic‑settings
- `services/` — клиент LLM, прайсинг
- `schemas.py` — Pydantic DTO для запроса/ответа

