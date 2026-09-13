import { useEffect, useState } from "react";
import { patients, charges as chargesApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { ConsultationCharge, PaymentMethod } from "../api/types";
import "./ClinicalCard.css";
import "./FinanceCard.css";

function brl(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function toCents(v: string): number | null {
  const n = Number(v.replace(/\./g, "").replace(",", "."));
  return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : null;
}
function when(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

const STATUS_LABEL: Record<string, string> = {
  pending: "A receber",
  received: "Recebido",
  cancelled: "Cancelado",
};
const METHODS: { v: PaymentMethod; label: string }[] = [
  { v: "pix", label: "PIX" },
  { v: "dinheiro", label: "Dinheiro" },
  { v: "cartao", label: "Cartão" },
  { v: "convenio", label: "Convênio" },
];

export function FinanceCard({ patientId }: { patientId: string }) {
  const [list, setList] = useState<ConsultationCharge[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [valueInput, setValueInput] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setError(null);
    patients
      .charges(patientId)
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar o financeiro."));
  }
  useEffect(load, [patientId]);

  async function patch(id: string, body: Parameters<typeof chargesApi.update>[1]) {
    setBusy(true);
    setError(null);
    try {
      await chargesApi.update(id, body);
      setEditing(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }

  async function saveValue(id: string) {
    const cents = toCents(valueInput);
    if (cents == null) return;
    await patch(id, { gross_cents: cents });
  }

  const pending = (list ?? []).filter((c) => c.status === "pending");
  const totalReceber = pending.reduce((s, c) => s + c.doctor_cents, 0);
  const totalRecebido = (list ?? [])
    .filter((c) => c.status === "received")
    .reduce((s, c) => s + c.doctor_cents, 0);

  return (
    <div className="card">
      <div className="hd">
        <span aria-hidden>💰</span>
        <h4>Financeiro</h4>
      </div>
      <div className="bd">
        {error ? <span className="muted">{error}</span> : null}
        {list == null ? (
          <div className="state"><div className="spinner" /></div>
        ) : list.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>
            Nenhum lançamento ainda. Ao marcar uma consulta como <b>realizada</b>, o valor entra aqui.
          </span>
        ) : (
          <>
            <div className="fin-totals">
              <div className="fin-total">
                <span className="fin-total-lab">A receber</span>
                <b className="fin-total-val warn">{brl(totalReceber)}</b>
              </div>
              <div className="fin-total">
                <span className="fin-total-lab">Recebido</span>
                <b className="fin-total-val ok">{brl(totalRecebido)}</b>
              </div>
            </div>

            <ul className="fin-list">
              {list.map((c) => (
                <li key={c.id} className={`fin-item st-${c.status}`}>
                  <div className="fin-row">
                    <span className={`fin-badge ${c.kind}`}>
                      {c.kind === "convenio" ? c.health_plan_name ?? "Convênio" : "Particular"}
                    </span>
                    <span className="fin-date">{when(c.created_at)}</span>
                    <span className={`fin-status st-${c.status}`}>{STATUS_LABEL[c.status]}</span>
                  </div>
                  <div className="fin-row">
                    <span className="fin-value">
                      {brl(c.doctor_cents)}
                      {c.kind === "convenio" && c.gross_cents !== c.doctor_cents ? (
                        <span className="muted"> (consulta {brl(c.gross_cents)})</span>
                      ) : null}
                    </span>
                    {c.payment_method ? <span className="muted">· {c.payment_method}</span> : null}
                  </div>

                  {editing === c.id ? (
                    <div className="fin-edit">
                      <input
                        inputMode="decimal"
                        value={valueInput}
                        onChange={(e) => setValueInput(e.target.value)}
                        placeholder="valor da consulta (R$)"
                      />
                      <button className="mini" disabled={busy} onClick={() => saveValue(c.id)}>Salvar</button>
                      <button className="mini" disabled={busy} onClick={() => setEditing(null)}>Cancelar</button>
                    </div>
                  ) : c.status !== "cancelled" ? (
                    <div className="fin-actions">
                      <button
                        className="mini"
                        onClick={() => {
                          setValueInput(String(c.gross_cents / 100));
                          setEditing(c.id);
                        }}
                      >
                        Editar valor
                      </button>
                      {c.status === "pending" ? (
                        <>
                          {METHODS.map((m) => (
                            <button
                              key={m.v}
                              className="mini ok"
                              disabled={busy}
                              onClick={() => patch(c.id, { status: "received", payment_method: m.v })}
                            >
                              Recebi · {m.label}
                            </button>
                          ))}
                          <button className="mini danger" disabled={busy} onClick={() => patch(c.id, { status: "cancelled" })}>
                            Cancelar
                          </button>
                        </>
                      ) : (
                        <button className="mini" disabled={busy} onClick={() => patch(c.id, { status: "pending" })}>
                          Reabrir
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="fin-actions">
                      <button className="mini" disabled={busy} onClick={() => patch(c.id, { status: "pending" })}>
                        Reabrir
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
