"""Observabilidade e health checks: liveness/readiness, request_id e log JSON."""

from __future__ import annotations

import json
import logging

import httpx

from app.core.logging import JsonFormatter, request_id_var


# ---------- Health checks ----------
async def test_liveness_does_not_touch_db(client: httpx.AsyncClient):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


async def test_readiness_ok_when_db_reachable(client: httpx.AsyncClient):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "reachable"}


# ---------- Correlação por request_id ----------
async def test_response_carries_request_id(client: httpx.AsyncClient):
    r = await client.get("/health/live")
    assert r.headers.get("X-Request-ID")


async def test_incoming_request_id_is_reused(client: httpx.AsyncClient):
    r = await client.get("/health/live", headers={"X-Request-ID": "corr-123"})
    assert r.headers["X-Request-ID"] == "corr-123"


# ---------- Formato de log JSON ----------
def test_json_formatter_includes_request_id_and_extra():
    formatter = JsonFormatter()
    token = request_id_var.set("req-abc")
    try:
        record = logging.LogRecord(
            name="flowra_care.access", level=logging.INFO, pathname=__file__, lineno=1,
            msg="request", args=(), exc_info=None,
        )
        record.status = 200
        record.path = "/health/live"
        line = formatter.format(record)
    finally:
        request_id_var.reset(token)

    parsed = json.loads(line)
    assert parsed["message"] == "request"
    assert parsed["level"] == "INFO"
    assert parsed["request_id"] == "req-abc"
    assert parsed["status"] == 200
    assert parsed["path"] == "/health/live"


def test_json_formatter_omits_request_id_when_absent():
    parsed = json.loads(JsonFormatter().format(logging.LogRecord(
        name="x", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="oi", args=(), exc_info=None,
    )))
    assert "request_id" not in parsed
    assert parsed["message"] == "oi"
