import { useEffect, useState } from "react";
import { patientApi, PatientApiError, type Answers, type Question } from "./api";

function range(min: number, max: number): number[] {
  const out: number[] = [];
  for (let i = min; i <= max; i++) out.push(i);
  return out;
}

const CHOICE_LABEL: Record<string, string> = {
  sim: "Sim",
  nao: "Não",
  "não": "Não",
  mais_ou_menos: "Mais ou menos",
  parcialmente: "Parcialmente",
};
function prettyChoice(c: string): string {
  return CHOICE_LABEL[c] ?? c;
}

function QuestionField({
  q,
  value,
  onChange,
}: {
  q: Question;
  value: string | number | undefined;
  onChange: (v: string | number) => void;
}) {
  let control;
  if (q.type === "scale") {
    const opts = range(q.options?.min ?? 0, q.options?.max ?? 10);
    control = (
      <div className="pt-chips">
        {opts.map((n) => (
          <button
            type="button"
            key={n}
            className={`pt-chip ${value === n ? "on" : ""}`}
            onClick={() => onChange(n)}
          >
            {n}
          </button>
        ))}
      </div>
    );
  } else if (q.type === "choice" || q.type === "boolean") {
    const choices = q.options?.choices ?? ["sim", "nao"];
    control = (
      <div className="pt-chips">
        {choices.map((c) => (
          <button
            type="button"
            key={c}
            className={`pt-chip ${value === c ? "on" : ""}`}
            onClick={() => onChange(c)}
          >
            {prettyChoice(c)}
          </button>
        ))}
      </div>
    );
  } else {
    control = (
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <input
          className="pt-input pt-num"
          inputMode="numeric"
          value={value === undefined ? "" : String(value)}
          onChange={(e) => {
            const digits = e.target.value.replace(/[^0-9]/g, "");
            if (digits === "") onChange("");
            else onChange(parseInt(digits, 10));
          }}
          placeholder="0"
        />
        {q.options?.unit ? <span className="pt-muted">{q.options.unit}</span> : null}
      </div>
    );
  }
  return (
    <div className="pt-q">
      <div className="pt-q-text">{q.text}</div>
      {control}
    </div>
  );
}

export function Checkin({ onDone, onCancel }: { onDone: (msg: string) => void; onCancel: () => void }) {
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [freeText, setFreeText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    patientApi
      .protocol()
      .then((p) => active && setQuestions([...p.questions].sort((a, b) => a.position - b.position)))
      .catch((e) =>
        active && setError(e instanceof PatientApiError ? e.message : "Falha ao carregar o check-in."),
      );
    return () => {
      active = false;
    };
  }, []);

  const structured = (questions ?? []).filter((q) => q.type !== "free_text");
  const freeTextQ = (questions ?? []).find((q) => q.type === "free_text");
  const missing = structured.filter(
    (q) => q.required && (answers[q.code] === undefined || answers[q.code] === ""),
  );
  const canSubmit = missing.length === 0 && !submitting && questions !== null;

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const clean: Answers = {};
      for (const [k, v] of Object.entries(answers)) if (v !== "") clean[k] = v;
      const res = await patientApi.submitCheckin(clean, freeText.trim() || null);
      onDone(res.message);
    } catch (e) {
      if (e instanceof PatientApiError && e.status === 409) {
        setSubmitError("Você já registrou seu check-in hoje.");
      } else {
        setSubmitError(e instanceof PatientApiError ? e.message : "Não foi possível enviar. Tente de novo.");
      }
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <div className="pt-card">
        <div className="pt-error">{error}</div>
        <button className="pt-btn ghost" style={{ marginTop: 12 }} onClick={onCancel}>
          Voltar
        </button>
      </div>
    );
  }
  if (!questions) {
    return (
      <div className="pt-center">
        <div className="pt-spinner" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
        <button className="pt-btn ghost small" onClick={onCancel}>
          Fechar
        </button>
        <h2 className="pt-h1" style={{ margin: 0, fontSize: 18 }}>
          Check-in de hoje
        </h2>
      </div>
      <div className="pt-card">
        {structured.map((q) => (
          <QuestionField
            key={q.code}
            q={q}
            value={answers[q.code]}
            onChange={(v) => setAnswers((prev) => ({ ...prev, [q.code]: v }))}
          />
        ))}
        {freeTextQ ? (
          <div className="pt-q">
            <div className="pt-q-text">{freeTextQ.text}</div>
            <textarea
              className="pt-textarea"
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="Opcional…"
            />
          </div>
        ) : null}
        {submitError ? <div className="pt-error" style={{ marginBottom: 10 }}>{submitError}</div> : null}
        <button className="pt-btn" onClick={submit} disabled={!canSubmit}>
          {submitting
            ? "Enviando…"
            : canSubmit
              ? "Enviar check-in"
              : `Responda ${missing.length} pergunta(s)`}
        </button>
      </div>
    </div>
  );
}
