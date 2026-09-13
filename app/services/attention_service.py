"""Triagem "Quem precisa de atenção hoje".

Combina, em poucas consultas em lote (sem N+1), os sinais que fazem um paciente
merecer atenção do médico agora — alertas em aberto, risco atual, escala
sinalizada, inatividade e adesão baixa — atribui uma pontuação e devolve, por
paciente, os motivos legíveis. É um facilitador de triagem: não diagnostica,
apenas prioriza o que já foi registrado.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clinical.scales import get_scale
from app.models.alert import Alert
from app.models.enums import AlertStatus, AlertUrgency, MedicationIntakeStatus, RiskLevel
from app.models.medication import MedicationIntake
from app.models.patient import Patient
from app.models.scale_entry import ScaleEntry
from app.models.scale_target import ScaleTarget
from app.services.inactivity_service import days_since_checkin, is_inactive

# Pesos de cada sinal (maior = mais urgente). Um alerta imediato em aberto é o
# sinal mais forte; a adesão baixa, o mais fraco.
_W_ALERT_IMMEDIATE = 100
_W_ALERT_ROUTINE = 35
_W_RISK_RED = 50
_W_RISK_ORANGE = 25
_W_SCALE_FLAGGED = 45
_W_SCALE_OFF_TARGET = 30
_W_INACTIVE = 35
_W_ADHERENCE = 25

_ADHERENCE_DAYS = 30
_ADHERENCE_MIN_RESPONSES = 4  # amostra mínima para falar de adesão
_ADHERENCE_LOW = 0.6


def _scale_short_name(code: str) -> str:
    scale = get_scale(code)
    return scale.name.split(" — ")[0] if scale else code


async def compute_attention(
    session: AsyncSession, doctor_id: uuid.UUID, now: datetime | None = None
) -> list[dict]:
    """Pacientes do médico que precisam de atenção, ordenados por urgência.

    Só inclui quem tem ao menos um motivo (score > 0). Cada item traz
    ``score`` e ``reasons`` (código, texto e severidade para a cor).
    """
    now = now or datetime.now(timezone.utc)
    patients = list(
        (
            await session.execute(
                select(Patient).where(
                    Patient.doctor_id == doctor_id, Patient.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    if not patients:
        return []
    ids = [p.id for p in patients]

    # Alertas em aberto por paciente e urgência (uma consulta).
    alert_rows = (
        await session.execute(
            select(Alert.patient_id, Alert.urgency, func.count(Alert.id))
            .where(Alert.patient_id.in_(ids), Alert.status != AlertStatus.RESOLVED)
            .group_by(Alert.patient_id, Alert.urgency)
        )
    ).all()
    immediate: dict[uuid.UUID, int] = {}
    routine: dict[uuid.UUID, int] = {}
    for pid, urgency, count in alert_rows:
        if urgency == AlertUrgency.IMMEDIATE:
            immediate[pid] = count
        else:
            routine[pid] = routine.get(pid, 0) + count

    # Última escala respondida por paciente (uma consulta; agrupa em memória).
    scale_rows = list(
        (
            await session.execute(
                select(ScaleEntry)
                .where(ScaleEntry.patient_id.in_(ids), ScaleEntry.status == "done")
                .order_by(ScaleEntry.completed_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_scale: dict[uuid.UUID, ScaleEntry] = {}
    latest_by_pc: dict[tuple[uuid.UUID, str], ScaleEntry] = {}
    for e in scale_rows:
        latest_scale.setdefault(e.patient_id, e)
        latest_by_pc.setdefault((e.patient_id, e.scale_code), e)

    # Metas (limiares) por paciente/escala — para sinalizar "fora da meta".
    target_rows = list(
        (await session.execute(select(ScaleTarget).where(ScaleTarget.patient_id.in_(ids))))
        .scalars()
        .all()
    )
    targets_by_patient: dict[uuid.UUID, list[ScaleTarget]] = {}
    for tg in target_rows:
        targets_by_patient.setdefault(tg.patient_id, []).append(tg)

    # Adesão à medicação nos últimos 30 dias por paciente (uma consulta).
    since = now - timedelta(days=_ADHERENCE_DAYS)
    intake_rows = (
        await session.execute(
            select(MedicationIntake.patient_id, MedicationIntake.status, func.count())
            .where(
                MedicationIntake.patient_id.in_(ids),
                MedicationIntake.scheduled_for >= since,
            )
            .group_by(MedicationIntake.patient_id, MedicationIntake.status)
        )
    ).all()
    taken: dict[uuid.UUID, int] = {}
    responded: dict[uuid.UUID, int] = {}
    for pid, status_, count in intake_rows:
        if status_ in (
            MedicationIntakeStatus.TAKEN,
            MedicationIntakeStatus.LATER,
            MedicationIntakeStatus.MISSED,
        ):
            responded[pid] = responded.get(pid, 0) + count
        if status_ == MedicationIntakeStatus.TAKEN:
            taken[pid] = count

    items: list[dict] = []
    for p in patients:
        reasons: list[dict] = []
        score = 0

        n_imm = immediate.get(p.id, 0)
        n_rot = routine.get(p.id, 0)
        if n_imm:
            score += _W_ALERT_IMMEDIATE * n_imm
            reasons.append({
                "code": "alert",
                "label": f"{n_imm} alerta(s) imediato(s) em aberto",
                "severity": "high",
            })
        if n_rot:
            score += _W_ALERT_ROUTINE * n_rot
            reasons.append({
                "code": "alert",
                "label": f"{n_rot} alerta(s) em aberto",
                "severity": "medium",
            })

        if p.current_risk == RiskLevel.RED:
            score += _W_RISK_RED
            reasons.append({"code": "risk", "label": "Risco alto 🔴", "severity": "high"})
        elif p.current_risk == RiskLevel.ORANGE:
            score += _W_RISK_ORANGE
            reasons.append(
                {"code": "risk", "label": "Acompanhamento 🟠", "severity": "medium"}
            )

        se = latest_scale.get(p.id)
        if se is not None and se.flagged:
            score += _W_SCALE_FLAGGED
            reasons.append({
                "code": "scale",
                "label": f"{_scale_short_name(se.scale_code)} sinalizou risco",
                "severity": "high",
            })

        # Fora da meta definida pelo médico (measurement-based care).
        for tg in targets_by_patient.get(p.id, []):
            latest = latest_by_pc.get((p.id, tg.scale_code))
            if latest is None or latest.score is None:
                continue
            scale = get_scale(tg.scale_code)
            worse = scale.higher_is_worse if scale else True
            off = latest.score > tg.target_score if worse else latest.score < tg.target_score
            if off:
                score += _W_SCALE_OFF_TARGET
                sign = ">" if worse else "<"
                reasons.append({
                    "code": "target",
                    "label": (
                        f"{_scale_short_name(tg.scale_code)} fora da meta "
                        f"({latest.score} {sign} {tg.target_score})"
                    ),
                    "severity": "medium",
                })

        if is_inactive(p, now):
            days = days_since_checkin(p, now)
            score += _W_INACTIVE
            reasons.append({
                "code": "inactive",
                "label": f"Sem check-in há {days} dia(s)",
                "severity": "medium",
            })

        n_resp = responded.get(p.id, 0)
        if n_resp >= _ADHERENCE_MIN_RESPONSES:
            rate = taken.get(p.id, 0) / n_resp
            if rate < _ADHERENCE_LOW:
                score += _W_ADHERENCE
                reasons.append({
                    "code": "adherence",
                    "label": f"Adesão baixa ({round(rate * 100)}%)",
                    "severity": "low",
                })

        if score > 0:
            items.append({
                "id": p.id,
                "name": p.name,
                "current_risk": p.current_risk,
                "last_checkin_at": p.last_checkin_at,
                "score": score,
                "reasons": reasons,
            })

    # Mais urgente primeiro; empate → risco maior → check-in mais antigo.
    items.sort(
        key=lambda i: (
            -i["score"],
            -i["current_risk"].order,
            i["last_checkin_at"] or datetime.min.replace(tzinfo=timezone.utc),
        )
    )
    return items
