"""Plano de assinatura — criado e ajustado pelo admin da plataforma.

O plano é um conceito **nosso** (nome, preço, limite de pacientes). O gateway
(Asaas) não guarda "planos": criamos uma assinatura com o valor/ciclo do plano
escolhido. Assim o admin ajusta preços aqui sem depender do gateway.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Plan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Preço em centavos (evita erro de ponto flutuante). Ex.: R$ 149,90 = 14990.
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Ciclo de cobrança. MVP: mensal (o Asaas usa MONTHLY/YEARLY).
    cycle: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    # Limite de pacientes ativos (None = ilimitado).
    patient_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Dias de teste grátis antes da 1ª cobrança (0 = sem teste).
    trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Inativar tira o plano da tela de assinatura sem apagar o histórico.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Ordem de exibição na tela de planos.
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
