import { useEffect, useState } from "react";
import { patients, prescriptions as rxApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Prescription, PrescriptionStatus } from "../api/types";
import { AddPrescriptionModal } from "./AddPrescriptionModal";
import { IconDoc } from "./icons";
import "./ClinicalCard.css";

const STATUS: Record<PrescriptionStatus, { label: string; cls: string }> = {
  draft: { label: "rascunho", cls: "b-muted" },
  issued: { label: "emitida", cls: "b-ok" },
  cancelled: { label: "cancelada", cls: "b-off" },
};

function summary(rx: Prescription): string {
  const items = rx.items ?? [];
  if (items.length === 0) return "—";
  const first = `${items[0].name} ${items[0].dose}`;
  return items.length > 1 ? `${first} +${items.length - 1}` : first;
}

export function PrescriptionsCard({ patientId }: { patientId: string }) {
  const [list, setList] = useState<Prescription[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  function load() {
    setError(null);
    patients
      .prescriptions(patientId)
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar as receitas."));
  }
  useEffect(load, [patientId]);

  async function act(rx: Prescription, action: "issue" | "cancel") {
    setBusy(rx.id);
    setActionError(null);
    try {
      const updated = action === "issue" ? await rxApi.issue(rx.id) : await rxApi.cancel(rx.id);
      setList((prev) => (prev ? prev.map((x) => (x.id === rx.id ? updated : x)) : prev));
    } catch (e) {
      setActionError(
        e instanceof ApiError
          ? e.status === 503
            ? "Emissão indisponível — configure o provedor de receita."
            : e.message
          : "Não foi possível concluir.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <div className="hd">
        <IconDoc width={16} height={16} color="var(--muted)" />
        <h4>Receitas</h4>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setShowAdd(true)}>
          + Nova receita
        </button>
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !list ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : list.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>Nenhuma receita.</span>
        ) : (
          <div className="clin-list">
            {list.map((rx) => {
              const st = STATUS[rx.status];
              return (
                <div className="clin-row" key={rx.id}>
                  <div className="clin-main">
                    <b>{summary(rx)}</b>
                    <span>
                      {(rx.items ?? []).length} item(ns)
                      {rx.issued_at
                        ? ` · ${new Date(rx.issued_at).toLocaleDateString("pt-BR")}`
                        : ""}
                    </span>
                  </div>
                  <span className={`badge ${st.cls}`}>{st.label}</span>
                  <div className="clin-actions">
                    {rx.status === "issued" && rx.pdf_url ? (
                      <a className="mini" href={rx.pdf_url} target="_blank" rel="noreferrer">
                        PDF
                      </a>
                    ) : null}
                    {rx.status === "draft" ? (
                      <>
                        <button className="mini" disabled={busy === rx.id} onClick={() => act(rx, "issue")}>
                          Emitir
                        </button>
                        <button className="mini danger" disabled={busy === rx.id} onClick={() => act(rx, "cancel")}>
                          Cancelar
                        </button>
                      </>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {actionError ? (
          <p className="muted" style={{ color: "var(--risk-red)", fontSize: 12.5, marginTop: 10 }}>{actionError}</p>
        ) : null}
      </div>

      {showAdd ? (
        <AddPrescriptionModal
          patientId={patientId}
          onClose={() => setShowAdd(false)}
          onCreated={() => {
            setShowAdd(false);
            load();
          }}
        />
      ) : null}
    </div>
  );
}
