# syntax=docker/dockerfile:1

# Use a slim Python image; psycopg2-binary has wheels for this
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python deps for PromptBuilder only
COPY PromptBuilder/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# Copy service code and prompts (PromptBuilder reads prompts from repo-root/prompts)
COPY PromptBuilder /app/PromptBuilder

# Optionally, you can COPY your .env here or mount it at runtime
# COPY PromptBuilder/.env.example /app/.env

EXPOSE 8010

# By default, FastAPI app lives at PromptBuilder.app.main:app
CMD ["uvicorn", "PromptBuilder.app.main:app", "--host", "0.0.0.0", "--port", "8010"]
