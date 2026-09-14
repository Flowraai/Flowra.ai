import { useState } from "react";
import type { PixCode } from "../api/types";
import "./NewPatientModal.css";
import "./PixModal.css";

function brl(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function PixModal({ pix, onClose }: { pix: PixCode; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(pix.payload);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard indisponível (contexto sem HTTPS): o paciente pode selecionar manualmente
      setCopied(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card pix-card" onClick={(e) => e.stopPropagation()}>
        <h3>PIX copia e cola</h3>
        <p className="muted pix-sub">
          {brl(pix.amount_cents)} · {pix.receiver} — {pix.city}
        </p>
        <textarea className="pix-code" readOnly value={pix.payload} rows={4} onFocus={(e) => e.target.select()} />
        <p className="muted pix-hint">
          Cobrança estática, sem gateway. Depois que o paciente pagar, marque como <b>recebido</b> aqui no financeiro.
        </p>
        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Fechar</button>
          <button type="button" className="btn" onClick={copy}>
            {copied ? "Copiado ✓" : "Copiar código"}
          </button>
        </div>
      </div>
    </div>
  );
}
