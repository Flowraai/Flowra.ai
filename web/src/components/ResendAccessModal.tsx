import { useState } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { PatientOnboarding } from "../api/types";
import "./NewPatientModal.css";

// Reenvia (e regenera) o acesso do paciente que perdeu o código/link.
export function ResendAccessModal({
  patientId,
  patientName,
  onClose,
}: {
  patientId: string;
  patientName: string;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PatientOnboarding | null>(null);
  const [copied, setCopied] = useState<"code" | "link" | null>(null);

  async function resend() {
    setBusy(true);
    setError(null);
    try {
      setResult(await patients.resendOnboarding(patientId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível gerar um novo acesso.");
    } finally {
      setBusy(false);
    }
  }

  async function copy(text: string, which: "code" | "link") {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      /* ignore */
    }
  }

  const hasLink = result?.onboarding_link?.startsWith("http");

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        {result ? (
          <div className="np-done">
            <div className="np-check">✓</div>
            <h3>Novo acesso gerado</h3>
            <p className="muted">
              {result.sent
                ? `Reenviamos o link de acesso para o contato de ${patientName}.`
                : `Não há contato para envio automático — repasse o acesso a ${patientName} manualmente.`}
            </p>
            <p className="muted np-hint" style={{ marginTop: 0 }}>
              ⚠️ O código anterior <b>deixou de funcionar</b>. Use o novo abaixo.
            </p>

            <div className="token-box">
              <code>{result.access_token}</code>
              <button className="btn sm" onClick={() => copy(result.access_token, "code")}>
                {copied === "code" ? "Copiado ✓" : "Copiar código"}
              </button>
            </div>

            {hasLink ? (
              <div className="token-box" style={{ marginTop: 8 }}>
                <code style={{ fontSize: 12, wordBreak: "break-all" }}>{result.onboarding_link}</code>
                <button className="btn sm" onClick={() => copy(result.onboarding_link, "link")}>
                  {copied === "link" ? "Copiado ✓" : "Copiar link"}
                </button>
              </div>
            ) : null}

            <button className="btn" onClick={onClose} style={{ marginTop: 12 }}>
              Concluir
            </button>
          </div>
        ) : (
          <div className="np-form">
            <h3>Reenviar acesso</h3>
            <p className="muted">
              Gera um <b>novo código de acesso</b> para <b>{patientName}</b> e reenvia o link ao contato
              cadastrado (WhatsApp/e-mail, conforme configurado).
            </p>
            <p className="muted np-hint" style={{ marginTop: 0 }}>
              Por segurança, o código antigo é invalidado — só o novo passa a funcionar.
            </p>

            {error ? <div className="np-error">{error}</div> : null}

            <div className="np-actions">
              <button type="button" className="btn ghost" onClick={onClose} disabled={busy}>
                Cancelar
              </button>
              <button type="button" className="btn" onClick={resend} disabled={busy}>
                {busy ? "Gerando…" : "Gerar e reenviar"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
