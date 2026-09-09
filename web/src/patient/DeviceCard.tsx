import { useEffect, useState } from "react";
import { patientApi, PatientApiError, type WearableSummary } from "./api";

function sleepLabel(min: number | null): string {
  if (min == null) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${h}h${String(m).padStart(2, "0")}`;
}
function num(v: number | null): string {
  return v == null ? "—" : v.toLocaleString("pt-BR");
}

export function DeviceCard() {
  const [data, setData] = useState<WearableSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setData(await patientApi.wearable());
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Falha ao carregar o dispositivo.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const res = await patientApi.wearableConnect();
      if (res.connect_url) {
        window.location.href = res.connect_url; // provedores OAuth (Terra/Fitbit)
        return;
      }
      await load();
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Não foi possível conectar.");
    } finally {
      setBusy(false);
    }
  }

  async function sync() {
    setBusy(true);
    try {
      setData(await patientApi.wearableSync());
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Não foi possível atualizar.");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!window.confirm("Desconectar seu dispositivo do Flowra Care?")) return;
    setBusy(true);
    try {
      await patientApi.wearableDisconnect();
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (loading) return null;

  const d = data;
  const latest = d?.latest;

  return (
    <div className="pt-card">
      <h3>⌚ Meu dispositivo</h3>
      {!d?.connected ? (
        <>
          <p className="pt-muted" style={{ marginTop: 4, marginBottom: 12 }}>
            Conecte seu relógio ou pulseira para acompanhar sono, batimentos e atividade junto do
            seu médico.
          </p>
          <button className="pt-btn" onClick={connect} disabled={busy}>
            {busy ? "Conectando…" : "Conectar dispositivo"}
          </button>
        </>
      ) : (
        <>
          <div className="dev-grid">
            <div className="dev-metric">
              <span className="dev-ico">😴</span>
              <b>{sleepLabel(latest?.sleep_minutes ?? null)}</b>
              <span className="pt-muted">sono</span>
            </div>
            <div className="dev-metric">
              <span className="dev-ico">❤️</span>
              <b>{num(latest?.resting_hr ?? null)}</b>
              <span className="pt-muted">bpm repouso</span>
            </div>
            <div className="dev-metric">
              <span className="dev-ico">📈</span>
              <b>{num(latest?.hrv_ms ?? null)}</b>
              <span className="pt-muted">HRV (ms)</span>
            </div>
            <div className="dev-metric">
              <span className="dev-ico">👟</span>
              <b>{num(latest?.steps ?? null)}</b>
              <span className="pt-muted">passos</span>
            </div>
          </div>
          <div className="dev-actions">
            <button className="pt-btn ghost small" onClick={sync} disabled={busy}>
              {busy ? "Atualizando…" : "Atualizar"}
            </button>
            <button className="pt-btn ghost small" onClick={disconnect} disabled={busy}>
              Desconectar
            </button>
          </div>
        </>
      )}
      {error ? <div className="pt-error" style={{ marginTop: 10 }}>{error}</div> : null}
    </div>
  );
}
