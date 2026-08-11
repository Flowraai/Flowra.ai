"""SEC-1 — derivação do IP do cliente para o rate limit (anti-spoof de XFF)."""

from __future__ import annotations

import types

from app.core.rate_limit import _client_ip


def _req(peer: str, xff: str | None = None):
    """Stub mínimo de Request (o _client_ip só usa client.host e headers.get)."""
    headers = {"x-forwarded-for": xff} if xff is not None else {}
    return types.SimpleNamespace(
        client=types.SimpleNamespace(host=peer),
        headers=headers,
    )


# 8.8.8.8 é um IP público de verdade (is_private=False em qualquer Python). NÃO usar
# a faixa de documentação 203.0.113.x: o Python 3.11 recente a trata como is_private.
def test_untrusted_peer_ignores_forwarded_for():
    # Cliente externo (IP público) conectando direto: o XFF forjado é ignorado,
    # vale o IP real do peer — senão trocar o header a cada request zeraria o balde.
    assert _client_ip(_req("8.8.8.8", xff="1.2.3.4")) == "8.8.8.8"


def test_trusted_proxy_uses_real_client_from_xff():
    # Peer é um proxy confiável (rede privada): o XFF é respeitado.
    assert _client_ip(_req("172.18.0.5", xff="8.8.8.8")) == "8.8.8.8"


def test_forged_prepended_xff_does_not_win():
    # O cliente prepende um IP falso; o proxy confiável anexa o IP real à direita.
    # Pegamos o IP não-confiável mais à direita (o real), não o forjado.
    assert _client_ip(_req("172.18.0.5", xff="1.2.3.4, 8.8.8.8")) == "8.8.8.8"


def test_skips_trusted_proxy_hops_from_right():
    # Cadeia com dois proxies: ignora os IPs privados à direita e devolve o cliente.
    assert _client_ip(_req("127.0.0.1", xff="8.8.8.8, 10.0.0.2")) == "8.8.8.8"


def test_no_xff_uses_peer():
    assert _client_ip(_req("8.8.8.8")) == "8.8.8.8"


def test_trust_disabled_uses_peer(monkeypatch):
    monkeypatch.setattr(
        "app.core.config.settings.rate_limit_trust_forwarded_for", False
    )
    assert _client_ip(_req("127.0.0.1", xff="8.8.8.8")) == "127.0.0.1"
