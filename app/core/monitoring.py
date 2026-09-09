"""Monitoramento de erros (Sentry) — opcional e seguro por padrão.

Só inicializa se `SENTRY_DSN` estiver definido. Sem a variável (ou sem o SDK
instalado), é um no-op — nada é enviado. Chamado no startup da API e do worker.

LGPD: `send_default_pii=False` (não anexa IP/cookies/headers às ocorrências) e
não capturamos corpo de requisição. Ainda assim, não coloque dado clínico em
mensagens de log/erro — o Sentry recebe a mensagem da exceção.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("flowra_care.monitoring")


def init_monitoring(component: str) -> bool:
    """Inicializa o Sentry se configurado. Retorna True se ligou."""
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:  # SDK ausente — segue sem monitoramento
        logger.warning("SENTRY_DSN definido, mas o pacote sentry-sdk não está instalado.")
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,  # LGPD: sem IP/cookies/headers
    )
    sentry_sdk.set_tag("component", component)
    logger.info("Monitoramento de erros ativo (Sentry)", extra={"component": component})
    return True
