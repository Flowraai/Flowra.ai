import { useEffect, useState } from "react";
import { healthPlans } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { HealthPlan, HealthPlanInput, PayoutType } from "../api/types";
import "./HealthPlansCard.css";

// Formata centavos → "R$ 1.234,56".
function brl(cents: number | null | undefined): string {
  if (cents == null) return "—";
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// "1.234,56" ou "1234.56" → centavos (int).
function toCents(v: string): number | null {
  const n = Number(v.replace(/\./g, "").replace(",", "."));
  return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : null;
}

const EMPTY = {
  name: "",
  ans_code: "",
  payout_type: "fixed" as PayoutType,
  payout_value: "",
  payout_percent: "",
  default_consultation: "",
};

export function HealthPlansCard() {
  const [plans, setPlans] = useState<HealthPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<typeof EMPTY | null>(null); // null = fechado
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setError(null);
    healthPlans
      .list(true)
      .then(setPlans)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar convênios."));
  }
  useEffect(load, []);

  function openNew() {
    setEditingId(null);
    setForm({ ...EMPTY });
  }
  function openEdit(p: HealthPlan) {
    setEditingId(p.id);
    setForm({
      name: p.name,
      ans_code: p.ans_code ?? "",
      payout_type: p.payout_type,
      payout_value: p.payout_value_cents != null ? String(p.payout_value_cents / 100) : "",
      payout_percent: p.payout_percent != null ? String(p.payout_percent) : "",
      default_consultation:
        p.default_consultation_cents != null ? String(p.default_consultation_cents / 100) : "",
    });
  }

  async function save() {
    if (!form || !form.name.trim()) return;
    const input: HealthPlanInput = {
      name: form.name.trim(),
      ans_code: form.ans_code.trim() || null,
      payout_type: form.payout_type,
      default_consultation_cents: toCents(form.default_consultation),
    };
    if (form.payout_type === "fixed") {
      input.payout_value_cents = toCents(form.payout_value);
    } else {
      input.payout_percent = form.payout_percent ? Number(form.payout_percent) : null;
    }
    setBusy(true);
    setError(null);
    try {
      if (editingId) await healthPlans.update(editingId, input);
      else await healthPlans.create(input);
      setForm(null);
      setEditingId(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível salvar o convênio.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(p: HealthPlan) {
    setBusy(true);
    try {
      if (p.active) await healthPlans.remove(p.id);
      else await healthPlans.update(p.id, { active: true });
      load();
    } finally {
      setBusy(false);
    }
  }

  function repasseLabel(p: HealthPlan): string {
    if (p.payout_type === "percentage") {
      return `${p.payout_percent ?? 0}% de ${brl(p.default_consultation_cents)}`;
    }
    return `${brl(p.payout_value_cents)} por consulta`;
  }

  return (
    <div className="card settings-card">
      <div className="hp-head">
        <div>
          <div className="set-section" style={{ marginTop: 0 }}>Convênios</div>
          <p className="muted set-hint" style={{ margin: 0 }}>
            Planos de saúde que você atende e o repasse por consulta. Pacientes sem convênio são
            particulares.
          </p>
        </div>
        {!form ? (
          <button className="btn sm" onClick={openNew}>+ Convênio</button>
        ) : null}
      </div>

      {error ? <div className="set-error">{error}</div> : null}

      {form ? (
        <div className="hp-form">
          <div className="set-row">
            <label>
              Nome
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Unimed, Bradesco Saúde…"
              />
            </label>
            <label>
              Registro ANS <span className="muted">(opcional)</span>
              <input
                value={form.ans_code}
                onChange={(e) => setForm({ ...form, ans_code: e.target.value })}
                placeholder="000000"
              />
            </label>
          </div>

          <label>
            Como você recebe por consulta
            <select
              value={form.payout_type}
              onChange={(e) => setForm({ ...form, payout_type: e.target.value as PayoutType })}
            >
              <option value="fixed">Valor fixo por consulta</option>
              <option value="percentage">Percentual sobre o valor de referência</option>
            </select>
          </label>

          <div className="set-row">
            {form.payout_type === "fixed" ? (
              <label>
                Valor do repasse (R$)
                <input
                  inputMode="decimal"
                  value={form.payout_value}
                  onChange={(e) => setForm({ ...form, payout_value: e.target.value })}
                  placeholder="90,00"
                />
              </label>
            ) : (
              <>
                <label>
                  Percentual (%)
                  <input
                    inputMode="numeric"
                    value={form.payout_percent}
                    onChange={(e) => setForm({ ...form, payout_percent: e.target.value })}
                    placeholder="70"
                  />
                </label>
                <label>
                  Valor de referência da consulta (R$)
                  <input
                    inputMode="decimal"
                    value={form.default_consultation}
                    onChange={(e) => setForm({ ...form, default_consultation: e.target.value })}
                    placeholder="150,00"
                  />
                </label>
              </>
            )}
          </div>
          {form.payout_type === "fixed" ? (
            <label>
              Valor de referência da consulta (R$) <span className="muted">(opcional)</span>
              <input
                inputMode="decimal"
                value={form.default_consultation}
                onChange={(e) => setForm({ ...form, default_consultation: e.target.value })}
                placeholder="150,00"
              />
            </label>
          ) : null}

          <div className="set-actions">
            <button className="btn" onClick={save} disabled={busy || !form.name.trim()}>
              {busy ? "Salvando…" : editingId ? "Salvar convênio" : "Adicionar convênio"}
            </button>
            <button className="btn ghost" onClick={() => { setForm(null); setEditingId(null); }} disabled={busy}>
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      {plans == null ? (
        <div className="state"><div className="spinner" /></div>
      ) : plans.length === 0 ? (
        <p className="muted" style={{ fontSize: 13 }}>
          Nenhum convênio cadastrado. Adicione os planos que você atende.
        </p>
      ) : (
        <ul className="hp-list">
          {plans.map((p) => (
            <li key={p.id} className={`hp-item ${p.active ? "" : "off"}`}>
              <div className="hp-main">
                <b>{p.name}</b>
                {p.ans_code ? <span className="muted"> · ANS {p.ans_code}</span> : null}
                {!p.active ? <span className="hp-tag">inativo</span> : null}
                <div className="hp-sub">{repasseLabel(p)}</div>
              </div>
              <div className="hp-actions">
                <button className="mini" onClick={() => openEdit(p)}>Editar</button>
                <button className="mini" onClick={() => toggleActive(p)} disabled={busy}>
                  {p.active ? "Inativar" : "Reativar"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
