"""Pesquisa (protocolo) editável por médico.

Cada tenant tem a **sua cópia** do protocolo — uma clonagem do template global
(seed), que o médico pode editar sem afetar os outros. As perguntas de segurança
(autoagressão, crise, medicação) são **protegidas**: dá para editar o texto/estilo,
mas não remover — o motor de risco depende dos códigos delas.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient import Patient
from app.models.protocol import Protocol, ProtocolQuestion
from app.protocol import psychiatry as P

# Perguntas cujos códigos alimentam sinais críticos de risco — não podem ser
# removidas nem ter o código alterado (o texto e o estilo continuam editáveis).
PROTECTED_CODES: frozenset[str] = frozenset(
    {P.Q_SELF_HARM, P.Q_CRISIS, P.Q_MEDICATION}
)

# Emojis padrão para escala, conforme a direção (o valor numérico é o que conta
# para o risco; o emoji é só a apresentação).
_EMOJI_BETTER = ["😣", "😟", "😐", "🙂", "😄"]   # maior valor = melhor (humor, sono)
_EMOJI_WORSE = ["😌", "🙂", "😐", "😟", "😰"]    # maior valor = pior (ansiedade)


def default_scale_emojis(minimum: int, maximum: int, direction: str | None) -> list[dict]:
    """5 emojis mapeados a valores igualmente espaçados em [min, max]."""
    emojis = _EMOJI_WORSE if direction == "higher_is_worse" else _EMOJI_BETTER
    n = len(emojis)
    span = maximum - minimum
    out = []
    for i, e in enumerate(emojis):
        value = minimum + round(span * i / (n - 1)) if span else minimum
        out.append({"emoji": e, "value": value})
    return out


def new_custom_code() -> str:
    return f"custom_{uuid.uuid4().hex[:8]}"


async def _global_default(session: AsyncSession) -> Protocol | None:
    result = await session.execute(
        select(Protocol)
        .where(
            Protocol.tenant_id.is_(None),
            Protocol.specialty == P.PSYCHIATRY_SPECIALTY,
            Protocol.is_active.is_(True),
        )
        .order_by(Protocol.created_at.desc())
        .options(selectinload(Protocol.questions))
    )
    return result.scalars().first()


async def get_tenant_protocol(session: AsyncSession, tenant_id: uuid.UUID) -> Protocol | None:
    result = await session.execute(
        select(Protocol)
        .where(Protocol.tenant_id == tenant_id, Protocol.is_active.is_(True))
        .order_by(Protocol.created_at.desc())
        .options(selectinload(Protocol.questions))
    )
    return result.scalars().first()


async def get_or_create_tenant_protocol(
    session: AsyncSession, tenant_id: uuid.UUID
) -> Protocol:
    """Protocolo do tenant; cria (clonando o template) na primeira vez e
    repontua os pacientes daquele tenant para a cópia."""
    existing = await get_tenant_protocol(session, tenant_id)
    if existing is not None:
        return existing

    template = await _global_default(session)
    if template is None:
        raise RuntimeError("Template de protocolo global não encontrado (rode o seed).")

    clone = Protocol(
        tenant_id=tenant_id,
        name=template.name,
        specialty=template.specialty,
        version=template.version,
        description=template.description,
        is_active=True,
    )
    session.add(clone)
    await session.flush()

    for q in sorted(template.questions, key=lambda x: x.position):
        session.add(
            ProtocolQuestion(
                protocol_id=clone.id,
                code=q.code,
                category=q.category,
                text=q.text,
                type=q.type,
                position=q.position,
                required=q.required,
                options=dict(q.options) if q.options else None,
            )
        )
    await session.flush()

    # Repontua os pacientes do tenant que ainda usam o template (ou nada) para a cópia.
    await session.execute(
        update(Patient)
        .where(
            Patient.tenant_id == tenant_id,
            (Patient.active_protocol_id == template.id) | (Patient.active_protocol_id.is_(None)),
        )
        .values(active_protocol_id=clone.id)
    )

    return await get_tenant_protocol(session, tenant_id)  # com as questions carregadas
