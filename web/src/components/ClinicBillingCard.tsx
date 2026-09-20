import { useEffect, useState, type FormEvent } from "react";
import { clinic } from "../api/endpoints";
import { ApiError } from "../api/client";

export function ClinicBillingCard() {
  const [centralized, setCentralized] = useState(false);
  const [pixKey, setPixKey] = useState("");
  const [pixCity, setPixCity] = useState("");
  const [receiver, setReceiver] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    clinic
      .billing()
      .then((b) => {
        setCentralized(b.pix_centralized);
        setPixKey(b.pix_key ?? "");
        setPixCity(b.pix_city ?? "");
        setReceiver(b.pix_receiver_name ?? "");
      })
      .catch(() => {
        /* mantém padrão */
      })
      .finally(() => setLoaded(true));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const b = await clinic.updateBilling({
        pix_centralized: centralized,
        pix_key: pixKey.trim() || null,
        pix_city: pixCity.trim() || null,
        pix_receiver_name: receiver.trim() || null,
      });
      setCentralized(b.pix_centralized);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return null;

  return (
    <div className="card settings-card">
      <form onSubmit={onSubmit}>
        <div className="set-section">Cobrança da clínica</div>
        <p className="muted set-hint">
          Recebimento centralizado: quando ligado, o PIX das cobranças particulares usa a chave da
          clínica (não a de cada médico). Útil quando a clínica recebe tudo e depois repassa. O
          rateio por médico continua registrado no Painel do gestor.
        </p>

        <label className="team-fin">
          <input
            type="checkbox"
            checked={centralized}
            onChange={(e) => setCentralized(e.target.checked)}
          />
          Centralizar o recebimento no PIX da clínica
        </label>

        <label>
          Chave PIX da clínica
          <input
            value={pixKey}
            onChange={(e) => setPixKey(e.target.value)}
            placeholder="CPF/CNPJ, telefone, e-mail ou chave aleatória"
          />
        </label>
        <label>
          Cidade
          <input value={pixCity} onChange={(e) => setPixCity(e.target.value)} placeholder="ex.: São Paulo" />
        </label>
        <label>
          Nome do recebedor <span className="muted">(opcional — usa o nome da clínica se vazio)</span>
          <input value={receiver} onChange={(e) => setReceiver(e.target.value)} />
        </label>

        {error ? <div className="set-error">{error}</div> : null}
        {saved ? <div className="set-saved">Alterações salvas ✓</div> : null}

        <div className="set-actions">
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Salvando…" : "Salvar cobrança"}
          </button>
        </div>
      </form>
    </div>
  );
}
