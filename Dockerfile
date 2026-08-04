# syntax=docker/dockerfile:1
# --- Estágio de build: instala as dependências num virtualenv isolado ---
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /app
COPY pyproject.toml ./
# Instala só as dependências de runtime (sem o grupo dev).
RUN pip install --upgrade pip && pip install .

# --- Estágio final: imagem enxuta, sem toolchain de build, usuário não-root ---
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    LOG_FORMAT=json \
    STORAGE_DIR=/data/uploads \
    WEB_CONCURRENCY=2

# Usuário sem privilégios + diretório de dados (uploads) com posse correta.
RUN useradd --create-home --uid 10001 flowra \
    && mkdir -p /data/uploads \
    && chown -R flowra:flowra /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=flowra:flowra . .
RUN chmod +x /app/docker-entrypoint.sh

USER flowra
EXPOSE 8000

# Healthcheck do container aponta para o readiness (verifica o banco).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live').status==200 else 1)"

# Entrypoint roda as migrações (e seed opcional) antes de subir a API.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--graceful-timeout", "30", \
     "--timeout", "60"]
