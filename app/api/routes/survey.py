"""Editor da pesquisa (protocolo) do médico.

O médico edita a **própria cópia** do protocolo: reordena, edita texto, ativa/
desativa, adiciona perguntas e alterna escala número/emoji. As perguntas de
segurança são protegidas (não removíveis).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import QuestionType
from app.models.protocol import ProtocolQuestion
from app.schemas.survey import (
    Survey,
    SurveyQuestion,
    SurveyQuestionCreate,
    SurveyQuestionUpdate,
    SurveyReorder,
)
from app.services.tenant_protocol import (
    PROTECTED_CODES,
    default_scale_emojis,
    get_or_create_tenant_protocol,
    new_custom_code,
)

router = APIRouter(prefix="/survey", tags=["survey"])


def _q_out(q: ProtocolQuestion) -> SurveyQuestion:
    return SurveyQuestion(
        id=q.id, code=q.code, category=q.category, text=q.text, type=q.type,
        position=q.position, required=q.required, options=q.options,
        protected=q.code in PROTECTED_CODES,
    )


async def _questions(session: AsyncSession, protocol_id: uuid.UUID) -> list[ProtocolQuestion]:
    """Perguntas direto do banco (evita coleção velha do identity-map após mutações)."""
    result = await session.execute(
        select(ProtocolQuestion)
        .where(ProtocolQuestion.protocol_id == protocol_id)
        .order_by(ProtocolQuestion.position)
    )
    return list(result.scalars().all())


async def _survey(session: AsyncSession, doctor: Doctor) -> Survey:
    protocol = await get_or_create_tenant_protocol(session, doctor.tenant_id)
    questions = await _questions(session, protocol.id)
    return Survey(id=protocol.id, name=protocol.name, questions=[_q_out(q) for q in questions])


async def _owned_question(
    session: AsyncSession, doctor: Doctor, question_id: uuid.UUID
) -> ProtocolQuestion:
    protocol = await get_or_create_tenant_protocol(session, doctor.tenant_id)
    q = await session.get(ProtocolQuestion, question_id)
    if q is None or q.protocol_id != protocol.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pergunta não encontrada.")
    return q


@router.get("", response_model=Survey)
async def get_survey(
    doctor: Doctor = Depends(get_current_doctor), session: AsyncSession = Depends(get_db)
) -> Survey:
    return await _survey(session, doctor)


@router.post("/questions", response_model=Survey, status_code=status.HTTP_201_CREATED)
async def add_question(
    payload: SurveyQuestionCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Survey:
    protocol = await get_or_create_tenant_protocol(session, doctor.tenant_id)
    options = dict(payload.options or {})
    if payload.type is QuestionType.SCALE:
        options.setdefault("min", 0)
        options.setdefault("max", 10)
        if options.get("scale_style") == "emoji" and not options.get("emojis"):
            options["emojis"] = default_scale_emojis(
                options["min"], options["max"], options.get("direction")
            )
    existing = await _questions(session, protocol.id)
    next_pos = max((q.position for q in existing), default=0) + 1
    session.add(
        ProtocolQuestion(
            protocol_id=protocol.id,
            code=new_custom_code(),
            category=payload.category,
            text=payload.text,
            type=payload.type,
            position=next_pos,
            required=payload.required,
            options=options or None,
        )
    )
    await session.flush()
    return await _survey(session, doctor)


@router.patch("/questions/{question_id}", response_model=Survey)
async def update_question(
    question_id: uuid.UUID,
    payload: SurveyQuestionUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Survey:
    q = await _owned_question(session, doctor, question_id)
    if payload.text is not None:
        q.text = payload.text
    if payload.category is not None:
        q.category = payload.category
    if payload.required is not None:
        q.required = payload.required
    if payload.position is not None:
        q.position = payload.position
    if payload.scale_style is not None and q.type is QuestionType.SCALE:
        opts = dict(q.options or {})
        if payload.scale_style == "emoji":
            opts["scale_style"] = "emoji"
            opts.setdefault("min", 0)
            opts.setdefault("max", 10)
            opts["emojis"] = default_scale_emojis(opts["min"], opts["max"], opts.get("direction"))
        else:
            opts["scale_style"] = "number"
            opts.pop("emojis", None)
        q.options = opts
    await session.flush()
    return await _survey(session, doctor)


@router.delete("/questions/{question_id}", response_model=Survey)
async def delete_question(
    question_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Survey:
    q = await _owned_question(session, doctor, question_id)
    if q.code in PROTECTED_CODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pergunta de segurança — pode ser editada, mas não removida.",
        )
    await session.delete(q)
    await session.flush()
    return await _survey(session, doctor)


@router.post("/reorder", response_model=Survey)
async def reorder(
    payload: SurveyReorder,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Survey:
    protocol = await get_or_create_tenant_protocol(session, doctor.tenant_id)
    by_id = {q.id: q for q in await _questions(session, protocol.id)}
    pos = 1
    for qid in payload.order:
        q = by_id.get(qid)
        if q is not None:
            q.position = pos
            pos += 1
    await session.flush()
    return await _survey(session, doctor)
