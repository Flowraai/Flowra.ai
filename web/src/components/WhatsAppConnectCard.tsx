import { useCallback, useEffect, useRef, useState } from "react";
import { whatsapp } from "../api/endpoints";
import { ApiError } from "../api/client";

export function WhatsAppConnectCard() {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false); // 503: Evolution não configurada
  const [qr, setQr] = useState<string | null>(null);
  const [pairing, setPairing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const s = await whatsapp.status();
      setConnected(s.connected);
      if (s.connected) {
        setQr(null);
        setPairing(null);
        stopPoll();
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setUnavailable(true);
      else setError(e instanceof ApiError ? e.message : "Falha ao consultar o WhatsApp.");
    } finally {
      setLoading(false);
    }
  }, [stopPoll]);

  useEffect(() => {
    loadStatus();
    return stopPoll;
  }, [loadStatus, stopPoll]);

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const res = await whatsapp.connect();
      setQr(res.qr);
      setPairing(res.pairing_code);
      if (res.state === "open") {
        setConnected(true);
        setQr(null);
      } else {
        // fica pareando: consulta o status a cada 3s até conectar
        stopPoll();
        pollRef.current = window.setInterval(loadStatus, 3000);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível gerar o QR.");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!window.confirm("Desconectar seu WhatsApp do Flowra Care?")) return;
    setBusy(true);
    try {
      await whatsapp.disconnect();
      setConnected(false);
      setQr(null);
      setPairing(null);
      stopPoll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível desconectar.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="card settings-card">
        <div className="set-section">Meu WhatsApp</div>
        <p className="muted">Carregando…</p>
      </div>
    );
  }

  if (unavailable) {
    return (
      <div className="card settings-card">
        <div className="set-section">Meu WhatsApp</div>
        <p className="muted set-hint">
          O envio por WhatsApp ainda não está habilitado no servidor. Peça ao administrador para
          configurar a Evolution API.
        </p>
      </div>
    );
  }

  return (
    <div className="card settings-card">
      <div className="set-section">Meu WhatsApp</div>
      <p className="muted set-hint">
        Conecte o seu número para que os <b>lembretes e o convite dos seus pacientes</b> saiam do seu
        WhatsApp. Recomendado usar um número <b>profissional</b> (não o pessoal).
      </p>

      {connected ? (
        <>
          <div className="set-saved">✓ WhatsApp conectado</div>
          <div className="set-actions">
            <button className="btn ghost" onClick={disconnect} disabled={busy}>
              Desconectar
            </button>
          </div>
        </>
      ) : qr ? (
        <div style={{ textAlign: "center" }}>
          <p className="muted set-hint">
            No celular: <b>WhatsApp → Aparelhos conectados → Conectar um aparelho</b> e aponte para o
            código abaixo.
          </p>
          <img
            src={qr}
            alt="QR code do WhatsApp"
            style={{ width: 240, height: 240, borderRadius: 12, background: "#fff", padding: 8 }}
          />
          {pairing ? (
            <p className="muted set-hint">
              Ou digite o código: <b style={{ letterSpacing: 2 }}>{pairing}</b>
            </p>
          ) : null}
          <p className="muted set-hint">Aguardando a leitura… (atualiza sozinho ao conectar)</p>
          <div className="set-actions" style={{ justifyContent: "center" }}>
            <button className="btn ghost" onClick={connect} disabled={busy}>
              Gerar novo QR
            </button>
          </div>
        </div>
      ) : (
        <div className="set-actions">
          <button className="btn" onClick={connect} disabled={busy}>
            {busy ? "Gerando QR…" : "Conectar meu WhatsApp"}
          </button>
        </div>
      )}

      {error ? <div className="set-error">{error}</div> : null}
    </div>
  );
}
