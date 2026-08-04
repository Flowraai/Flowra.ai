import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { IconChat, IconSearch } from "../components/icons";
import { useAsync } from "../lib/useAsync";
import { patients } from "../api/endpoints";
import { avatarGradient, initials, relativeDate } from "../lib/format";
import "./Messages.css";

export function Messages() {
  const navigate = useNavigate();
  const { data, loading, error } = useAsync(() => patients.list(), []);
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const list = [...(data ?? [])].sort((a, b) =>
      (b.last_checkin_at ?? "").localeCompare(a.last_checkin_at ?? ""),
    );
    if (!query.trim()) return list;
    return list.filter((p) => p.name.toLowerCase().includes(query.trim().toLowerCase()));
  }, [data, query]);

  return (
    <AppShell
      title="Mensagens"
      subtitle="Converse com seus pacientes"
      actions={
        <>
          <div className="search">
            <IconSearch width={15} height={15} />
            <input
              placeholder="Buscar paciente…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Buscar paciente"
            />
          </div>
          <ThemeToggle />
        </>
      }
    >
      <div className="panel">
        <div className="panel-head">
          <h3>Conversas</h3>
          <span className="hint">abra um paciente para ver e responder a thread</span>
        </div>
        {loading ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : error ? (
          <div className="state">
            <span className="err">{error}</span>
          </div>
        ) : rows.length === 0 ? (
          <div className="state">Nenhum paciente encontrado.</div>
        ) : (
          <div className="conv-list">
            {rows.map((p) => (
              <button key={p.id} className="conv-row" onClick={() => navigate(`/pacientes/${p.id}`)}>
                <div
                  className="pt-avatar"
                  style={{ width: 38, height: 38, fontSize: 13, background: avatarGradient(p.current_risk) }}
                >
                  {initials(p.name)}
                </div>
                <div className="conv-main">
                  <b>{p.name}</b>
                  <span className="muted">Último check-in: {relativeDate(p.last_checkin_at)}</span>
                </div>
                <IconChat width={18} height={18} color="var(--muted)" />
              </button>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
