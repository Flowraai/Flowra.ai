import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Certificate } from "../api/types";
import { CertificateModal } from "./CertificateModal";
import { IconDoc } from "./icons";
import "./ClinicalCard.css";

const KIND: Record<string, string> = {
  afastamento: "Atestado de afastamento",
  comparecimento: "Declaração de comparecimento",
};

function when(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

export function CertificatesCard({ patientId }: { patientId: string }) {
  const navigate = useNavigate();
  const [list, setList] = useState<Certificate[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  function load() {
    setError(null);
    patients
      .certificates(patientId)
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar os atestados."));
  }
  useEffect(load, [patientId]);

  return (
    <div className="card">
      <div className="hd">
        <IconDoc width={16} height={16} color="var(--muted)" />
        <h4>Atestados e declarações</h4>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setAdding(true)}>
          + Emitir
        </button>
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !list ? (
          <div className="state"><div className="spinner" /></div>
        ) : list.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>
            Nenhum atestado emitido. Emita afastamento ou declaração de comparecimento.
          </span>
        ) : (
          <div className="clin-list">
            {list.map((c) => (
              <div className="clin-row" key={c.id}>
                <div className="clin-main">
                  <b>{KIND[c.kind] ?? "Documento"}</b>
                  <span>
                    {c.kind === "afastamento" && c.days ? `${c.days} dia(s) · ` : ""}
                    {when(c.issued_at)}
                  </span>
                </div>
                <div className="clin-actions">
                  <button className="mini" onClick={() => navigate(`/pacientes/${patientId}/atestado/${c.id}`)}>
                    Abrir / Imprimir
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {adding ? (
        <CertificateModal
          patientId={patientId}
          onClose={() => setAdding(false)}
          onCreated={(certId) => navigate(`/pacientes/${patientId}/atestado/${certId}`)}
        />
      ) : null}
    </div>
  );
}
