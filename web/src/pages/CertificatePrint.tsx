import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { certificates, patients } from "../api/endpoints";
import type { Certificate, Patient } from "../api/types";
import "./PatientReport.css";

function longDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}
function dayOnly(d: string): string {
  return new Date(d + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

export function CertificatePrint() {
  const { id = "", certId = "" } = useParams();
  const navigate = useNavigate();
  const { doctor } = useAuth();
  const [cert, setCert] = useState<Certificate | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const [c, p] = await Promise.allSettled([certificates.get(certId), patients.get(id)]);
      if (!active) return;
      if (c.status === "fulfilled") setCert(c.value);
      if (p.status === "fulfilled") setPatient(p.value);
      setLoading(false);
    })();
    return () => { active = false; };
  }, [certId, id]);

  if (loading) return <div className="rep-loading"><div className="spinner" /> Gerando documento…</div>;
  if (!cert || !patient) return <div className="rep-loading">Documento não encontrado.</div>;

  const title = cert.kind === "afastamento" ? "ATESTADO MÉDICO" : "DECLARAÇÃO";
  const clinic = doctor?.clinic || doctor?.tenant_name || "Flowra Care";

  const body =
    cert.kind === "afastamento" ? (
      <>
        Atesto, para os devidos fins, que o(a) Sr(a). <b>{patient.name}</b> esteve sob meus cuidados
        e necessita de afastamento de suas atividades pelo período de <b>{cert.days} dia(s)</b>
        {cert.start_date ? <> a partir de <b>{dayOnly(cert.start_date)}</b></> : null}.
        {cert.cid ? <> CID: <b>{cert.cid}</b>.</> : null}
        {cert.notes ? <> {cert.notes}</> : null}
      </>
    ) : (
      <>
        Declaro, para os devidos fins, que o(a) Sr(a). <b>{patient.name}</b> compareceu a atendimento
        médico{cert.start_date ? <> em <b>{dayOnly(cert.start_date)}</b></> : <> nesta data</>}.
        {cert.notes ? <> {cert.notes}</> : null}
      </>
    );

  return (
    <div className="rep">
      <div className="rep-toolbar no-print">
        <button className="btn ghost" onClick={() => navigate(`/pacientes/${id}`)}>← Voltar</button>
        <button className="btn" onClick={() => window.print()}>Imprimir / Salvar em PDF</button>
      </div>

      <div className="rep-doc cert-doc">
        <header className="rep-head">
          <div>
            <div className="rep-clinic">{clinic}</div>
            <div className="rep-doctor">
              {doctor?.name}{doctor?.specialty ? ` — ${doctor.specialty}` : ""}
              {doctor?.council_id ? ` · ${doctor.council_id}` : ""}
            </div>
          </div>
        </header>

        <h1 className="cert-title">{title}</h1>

        <p className="cert-body">{body}</p>

        <p className="cert-place">
          {longDate(cert.issued_at)}.
        </p>

        <div className="cert-sign">
          <div className="cert-line" />
          <div>{doctor?.name}</div>
          <div className="rep-muted">
            {doctor?.specialty ? `${doctor.specialty}` : "Médico(a)"}{doctor?.council_id ? ` · ${doctor.council_id}` : ""}
          </div>
        </div>

        <footer className="rep-foot">
          Documento emitido pelo Flowra Care. A validade legal depende da assinatura do médico
          responsável. Dados sensíveis (LGPD) — trate com sigilo.
        </footer>
      </div>
    </div>
  );
}
