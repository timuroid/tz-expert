# syntax=docker/dockerfile:1

# Use a slim Python image
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python deps for LLMRequester only
COPY LLMRequester/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# Copy service code
COPY LLMRequester /app/LLMRequester

# Env is read from LLMRequester/llmrequester.env or LLMRequester/.env inside the image
# if present (see LLMRequester/core/settings.py). Keep secrets in those files (both are
# ignored by git) and they will be copied with the code when building the image.

EXPOSE 8020

# FastAPI app lives at LLMRequester.app.main:app
CMD ["uvicorn", "LLMRequester.app.main:app", "--host", "0.0.0.0", "--port", "8020"]
