"""Logging estruturado (JSON) com correlação por requisição (request_id).

Em produção (`LOG_FORMAT=json`) cada log vira uma linha JSON — pronta para
agregadores (CloudWatch, Loki, Datadog...). Em dev (`LOG_FORMAT=text`), formato
legível. O `request_id` corrente é injetado automaticamente via contextvar.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar

from app.core.config import settings

# request_id da requisição em andamento (preenchido pelo middleware).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Campos extras passados via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


class _RequestIdTextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def setup_logging() -> None:
    """Configura o root logger conforme LOG_LEVEL/LOG_FORMAT (idempotente)."""
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler()
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.addFilter(_RequestIdTextFilter())
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
        )

    root.handlers = [handler]
