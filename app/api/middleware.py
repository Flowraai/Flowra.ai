"""Middlewares HTTP: correlação por request_id e log de acesso estruturado."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var

logger = logging.getLogger("flowra_care.access")

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Atribui um request_id (reaproveita o do cabeçalho, se houver), registra a
    requisição e devolve o id no cabeçalho da resposta para correlação ponta a ponta."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(_REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            response.headers[_REQUEST_ID_HEADER] = request_id
            # Não logamos query string nem corpo (podem conter dado sensível — LGPD).
            logger.info(
                "request",
                extra={"method": request.method, "path": request.url.path,
                       "status": response.status_code, "duration_ms": duration_ms},
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.exception(
                "request_failed",
                extra={"method": request.method, "path": request.url.path,
                       "duration_ms": duration_ms},
            )
            raise
        finally:
            request_id_var.reset(token)
