# PromptBuilder — сервис сборки промптов для LLM

Русскоязычная документация по сервису PromptBuilder. Сервис формирует понятные и строгие промпты (system+user) для двухшагового пайплайна анализа документа LLM‑моделью и возвращает JSON Schema, чтобы принудить модель выдавать валидный JSON.

## Кратко о назначении
- Шаг 1 (GroupResult): для каждой группы правил из каталога (GG) строятся пары сообщений system/user и схема JSON результата. Модель должна вернуть, какие ошибки (по кодам) найдены, как они проверялись, и «инстансы» с привязкой к строкам/секциям.
- Шаг 2 (SectionPlanOutput): по результатам шага 1 строится промпт для финального план‑отчёта по разделам документа (с группировкой инстансов и дедупликацией).

## Архитектура папки
- `app/` — FastAPI-приложение
  - `main.py` — инициализация сервиса, middleware access‑логов, подключение роутов
  - `routers.py` — HTTP‑эндпоинты `/v1/prompt-builder/step1/build`, `/v1/prompt-builder/step2/build`
- `services/` — бизнес‑логика
  - `builder.py` — сборка DTO для шагов (items, schema) и конвертация в ответы API
  - `repository.py` — чтение каталога правил/групп из БД (только read‑only)
  - `templates.py` — загрузка шаблонов и рендер текстов промптов
- `core/` — инфраструктура
  - `settings.py` — конфигурация через переменные окружения (pydantic‑settings)
  - `db.py` — SQLAlchemy engine/session
  - `logging.py` — настройка логирования и привязка `request_id` к логам
- `models/` — ORM‑модели SQLAlchemy для таблиц каталога
- `schemas.py` — все Pydantic‑модели:
  - DTO API (Step1BuildRequest/Response, Step2BuildRequest/Response, BuildItem, StepPrompt)
  - доменные результаты (GroupResult/Step1GroupResult, SectionPlanOutput)
- `prompts/` — markdown‑шаблоны промптов: `step1.system.md`, `step1_user.tpl.md`, `step2.system.md`, `step2_user.tpl.md`

## Эндпоинты
Базовый префикс: `/v1/prompt-builder`

- `POST /step1/build`
  - Вход: `Step1BuildRequest { markdown: str, ggid: int, limit?: int }`
  - Выход: `Step1BuildResponse { ggid, items: BuildItem[], schema, groups? }`
  - Назначение: вернуть список system/user сообщений на группу и JSON Schema результата шага 1.

- `POST /step2/build`
  - Вход: `Step2BuildRequest { markdown: str, step1_results: str(JSON) }`
  - Выход: `Step2BuildResponse { prompt: StepPrompt, schema }`
  - Назначение: собрать system/user сообщения для шага 2 и схему SectionPlanOutput.

Примечания:
- Для шага 1 поле `schema` — это именованная JSON Schema из Pydantic‑модели GroupResult с усиленными required.
- Для шага 2 поле `schema` — JSON Schema из Pydantic‑модели SectionPlanOutput.

## Конфигурация (env)
Сервис читает `.env` в текущей рабочей директории и переменные с префиксом `PB_`:

- `PB_DATABASE_URL` — строка подключения к БД каталога (PostgreSQL)
- `PB_LOG_LEVEL` — уровень логирования (по умолчанию `INFO`)
- `PB_LOG_JSON` — `true/false` для JSON‑логов (по умолчанию `false`)

Пример `.env`:
```
PB_DATABASE_URL=postgresql://user:pass@host:5432/db
PB_LOG_LEVEL=INFO
PB_LOG_JSON=false
```

## Логирование
- Настройка в `core/logging.py`, активация в `app/main.py`.
- Middleware проставляет `X-Request-ID` (или генерирует), логирует `request.start` / `request.end` / `request.error` с временем.
- Все логи содержат `rid=<request_id>` для корреляции.
- Формат настраивается через `PB_LOG_JSON` (чистый текст или JSON).

## Алгоритм работы
1. Клиент вызывает `POST /step1/build` с исходным markdown и `ggid`.
2. `builder` получает группы и правила из `repository`, рендерит тексты по шаблонам `templates` и возвращает JSON Schema результата (GroupResult).
3. Клиент вызывает LLMRequester, передаёт messages и schema, получает валидный JSON.
4. Клиент вызывает `POST /step2/build`, передаёт исходный markdown и JSON результата шага 1; получает промпт и schema SectionPlanOutput.
5. LLMRequester возвращает валидный JSON отчёта по разделам.


## Запуск

Локально (из корня репозитория):
```
uvicorn PromptBuilder.app.main:app --reload --port 8010
```

Docker:
```
docker build -t prompt-builder -f PromptBuilder/Dockerfile .
docker run --rm -p 8010:8010 --env-file PromptBuilder/.env prompt-builder
```

## Структура БД (упрощённо)
- `error_group_groups` (GG): набор «каталогов» групп правил.
- `error_groups`: группы правил (имя, код, описание, признак удаления, связь с GG).
- `errors`: отдельные правила (код, имя, описание, детектор, связь с группой).

## Разработка
- Код стильно разбит по слоям: `app` → `services` → `core/models`.
- Не меняйте формат текстов шаблонов без согласования — промпты стабильны по формату.
- Перед коммитом проверьте, что JSON Schema соответствует ожидаемой структуре (особенно для новых полей).

