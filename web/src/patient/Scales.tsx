import { useEffect, useState } from "react";
import { patientApi, PatientApiError, type ScalePending } from "./api";

export function PatientScales() {
  const [pending, setPending] = useState<ScalePending[]>([]);
  const [active, setActive] = useState<ScalePending | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ message: string; safety: string | null } | null>(null);

  async function load() {
    try {
      setPending(await patientApi.pendingScales());
    } catch {
      /* silencioso */
    }
  }
  useEffect(() => {
    load();
  }, []);

  function open(p: ScalePending) {
    setActive(p);
    setAnswers(new Array(p.scale.items.length).fill(null));
    setError(null);
    setDone(null);
  }

  async function submit() {
    if (!active || answers.some((a) => a === null)) return;
    setBusy(true);
    setError(null);
    try {
      const res = await patientApi.submitScale(active.id, answers as number[]);
      setDone({ message: res.message, safety: res.safety });
      setActive(null);
      await load();
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Não foi possível enviar.");
    } finally {
      setBusy(false);
    }
  }

  // Tela de conclusão (com orientação de segurança, se houver).
  if (done) {
    return (
      <div className="pt-card">
        <h3>✓ Questionário enviado</h3>
        <p className="pt-muted" style={{ marginTop: 4 }}>{done.message}</p>
        {done.safety ? (
          <div className="pt-error" style={{ marginTop: 10 }}>{done.safety}</div>
        ) : null}
        <button className="pt-btn ghost small" style={{ marginTop: 12 }} onClick={() => setDone(null)}>
          Fechar
        </button>
      </div>
    );
  }

  // Formulário da escala ativa.
  if (active) {
    const sc = active.scale;
    return (
      <div className="pt-card">
        <h3>{sc.name}</h3>
        <p className="pt-muted" style={{ marginTop: 4, marginBottom: 12 }}>{sc.period}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {sc.items.map((item, i) => (
            <div key={i}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>
                {i + 1}. {item}
              </div>
              <div className="scale-opts">
                {sc.options.map((opt, v) => (
                  <button
                    key={v}
                    className={`scale-opt ${answers[i] === v ? "on" : ""}`}
                    onClick={() => setAnswers((prev) => prev.map((x, idx) => (idx === i ? v : x)))}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        {error ? <div className="pt-error" style={{ marginTop: 12 }}>{error}</div> : null}
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button className="pt-btn" onClick={submit} disabled={busy || answers.some((a) => a === null)}>
            {busy ? "Enviando…" : "Enviar respostas"}
          </button>
          <button className="pt-btn ghost small" onClick={() => setActive(null)} disabled={busy}>
            Voltar
          </button>
        </div>
      </div>
    );
  }

  if (pending.length === 0) return null;

  return (
    <div className="pt-card">
      <h3>📋 Questionários</h3>
      <p className="pt-muted" style={{ marginTop: 4, marginBottom: 10 }}>
        Seu médico pediu que você responda:
      </p>
      {pending.map((p) => (
        <div className="pt-dose" key={p.id}>
          <div className="pt-dose-info">
            <b>{p.scale.name}</b>
            <div className="pt-muted">{p.scale.items.length} perguntas · menos de 2 min</div>
          </div>
          <button className="pt-btn ghost small" onClick={() => open(p)}>Responder</button>
        </div>
      ))}
    </div>
  );
}
