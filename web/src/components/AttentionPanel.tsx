import { useNavigate } from "react-router-dom";
import { RiskBadge } from "./RiskBadge";
import { useAsync } from "../lib/useAsync";
import { patients } from "../api/endpoints";
import { avatarGradient, initials, relativeDate } from "../lib/format";
import type { AttentionItem, AttentionReason } from "../api/types";
import "./AttentionPanel.css";

// Ícone por tipo de motivo — leitura rápida sem depender só da cor.
const REASON_ICON: Record<AttentionReason["code"], string> = {
  alert: "🚨",
  risk: "▲",
  scale: "📋",
  inactive: "🕗",
  adherence: "💊",
};

export function AttentionPanel({ reloadKey }: { reloadKey: number }) {
  const navigate = useNavigate();
  const { data, loading, error } = useAsync(() => patients.attention(), [reloadKey]);
  const items = data ?? [];

  return (
    <section className="attn">
      <div className="attn-head">
        <h3>Quem precisa de atenção hoje</h3>
        {!loading && !error ? (
          <span className="attn-count">{items.length}</span>
        ) : null}
      </div>

      {loading ? (
        <div className="attn-state">
          <div className="spinner" />
        </div>
      ) : error ? (
        <div className="attn-state">
          <span className="err">{error}</span>
        </div>
      ) : items.length === 0 ? (
        <div className="attn-empty">
          <span className="attn-empty-ic">✓</span>
          Tudo em dia hoje — nenhum paciente com sinal de atenção.
        </div>
      ) : (
        <div className="attn-list">
          {items.map((it) => (
            <AttentionCard key={it.id} it={it} onOpen={() => navigate(`/pacientes/${it.id}`)} />
          ))}
        </div>
      )}
    </section>
  );
}

function AttentionCard({ it, onOpen }: { it: AttentionItem; onOpen: () => void }) {
  // A severidade do primeiro motivo (o de maior peso) dá a cor da faixa.
  const top = it.reasons[0]?.severity ?? "medium";
  return (
    <button className={`attn-card sev-${top}`} onClick={onOpen}>
      <span className="attn-stripe" />
      <div className="attn-card-top">
        <div
          className="pt-avatar"
          style={{ width: 36, height: 36, fontSize: 13, background: avatarGradient(it.current_risk) }}
        >
          {initials(it.name)}
        </div>
        <div className="attn-name">
          <b>{it.name}</b>
          <span className="muted">{relativeDate(it.last_checkin_at)}</span>
        </div>
        <RiskBadge level={it.current_risk} />
      </div>
      <ul className="attn-reasons">
        {it.reasons.map((r, i) => (
          <li key={i} className={`attn-reason sev-${r.severity}`}>
            <span className="attn-reason-ic" aria-hidden>
              {REASON_ICON[r.code]}
            </span>
            {r.label}
          </li>
        ))}
      </ul>
    </button>
  );
}
