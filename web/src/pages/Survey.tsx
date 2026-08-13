import { useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { survey as surveyApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { QuestionType, Survey, SurveyQuestion } from "../api/types";
import "./Survey.css";

const TYPE_LABEL: Record<QuestionType, string> = {
  scale: "Escala",
  integer: "Número",
  choice: "Múltipla escolha",
  boolean: "Sim/Não",
  free_text: "Texto livre",
};

export function SurveyPage() {
  const [data, setData] = useState<Survey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  // formulário de nova pergunta
  const [newText, setNewText] = useState("");
  const [newType, setNewType] = useState<QuestionType>("scale");
  const [newChoices, setNewChoices] = useState("sim, nao");

  async function refresh() {
    try {
      setData(await surveyApi.get());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao carregar a pesquisa.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function run(fn: () => Promise<Survey>) {
    setBusy(true);
    setError(null);
    try {
      setData(await fn());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }

  const questions = data ? [...data.questions].sort((a, b) => a.position - b.position) : [];

  function move(idx: number, dir: -1 | 1) {
    const next = idx + dir;
    if (next < 0 || next >= questions.length) return;
    const order = questions.map((q) => q.id);
    [order[idx], order[next]] = [order[next], order[idx]];
    run(() => surveyApi.reorder(order));
  }

  function saveText(q: SurveyQuestion) {
    const text = draft.trim();
    setEditing(null);
    if (text && text !== q.text) run(() => surveyApi.updateQuestion(q.id, { text }));
  }

  function addQuestion() {
    if (!newText.trim()) return;
    const options: Record<string, unknown> =
      newType === "scale"
        ? { min: 0, max: 10 }
        : newType === "choice"
          ? { choices: newChoices.split(",").map((c) => c.trim()).filter(Boolean) }
          : newType === "boolean"
            ? { choices: ["sim", "nao"] }
            : {};
    run(() =>
      surveyApi.addQuestion({ text: newText.trim(), type: newType, options }),
    ).then(() => {
      setNewText("");
      setNewChoices("sim, nao");
      setNewType("scale");
    });
  }

  return (
    <AppShell
      title="Pesquisa"
      subtitle="As perguntas do check-in diário dos seus pacientes"
      actions={<ThemeToggle />}
    >
      <div className="survey-wrap">
        <p className="muted survey-hint">
          Personalize a pesquisa da sua clínica: edite o texto, reordene, ative/desative a
          obrigatoriedade, troque a escala numérica por emoji e adicione perguntas. As perguntas de
          <b> segurança</b> (autoagressão, crise, medicação) podem ser editadas, mas não removidas.
        </p>

        {error ? <div className="set-error">{error}</div> : null}

        {!data ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : (
          <>
            <div className="card survey-list">
              {questions.map((q, idx) => {
                const isScale = q.type === "scale";
                const isEmoji = isScale && q.options?.scale_style === "emoji";
                return (
                  <div className="survey-q" key={q.id}>
                    <div className="survey-reorder">
                      <button disabled={busy || idx === 0} onClick={() => move(idx, -1)} aria-label="Subir">↑</button>
                      <button disabled={busy || idx === questions.length - 1} onClick={() => move(idx, 1)} aria-label="Descer">↓</button>
                    </div>
                    <div className="survey-main">
                      {editing === q.id ? (
                        <input
                          className="survey-edit"
                          value={draft}
                          autoFocus
                          onChange={(e) => setDraft(e.target.value)}
                          onBlur={() => saveText(q)}
                          onKeyDown={(e) => e.key === "Enter" && saveText(q)}
                        />
                      ) : (
                        <button
                          className="survey-text"
                          onClick={() => {
                            setEditing(q.id);
                            setDraft(q.text);
                          }}
                          title="Clique para editar"
                        >
                          {q.text}
                        </button>
                      )}
                      <div className="survey-meta">
                        <span className="chip-tag">{TYPE_LABEL[q.type]}</span>
                        <span className="chip-tag ghost">{q.category}</span>
                        {q.protected ? <span className="chip-tag safe">segurança</span> : null}
                        {q.required ? <span className="chip-tag ghost">obrigatória</span> : null}
                      </div>
                    </div>
                    <div className="survey-actions">
                      {isScale ? (
                        <button
                          className="mini"
                          disabled={busy}
                          onClick={() =>
                            run(() =>
                              surveyApi.updateQuestion(q.id, {
                                scale_style: isEmoji ? "number" : "emoji",
                              }),
                            )
                          }
                        >
                          {isEmoji ? "→ números" : "→ emoji"}
                        </button>
                      ) : null}
                      <button
                        className="mini"
                        disabled={busy}
                        onClick={() =>
                          run(() => surveyApi.updateQuestion(q.id, { required: !q.required }))
                        }
                      >
                        {q.required ? "tornar opcional" : "tornar obrigatória"}
                      </button>
                      {!q.protected ? (
                        <button
                          className="mini danger"
                          disabled={busy}
                          onClick={() => {
                            if (window.confirm(`Excluir "${q.text}"?`)) {
                              run(() => surveyApi.deleteQuestion(q.id));
                            }
                          }}
                        >
                          excluir
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="card survey-add">
              <div className="set-section">Adicionar pergunta</div>
              <label>
                Pergunta
                <input
                  value={newText}
                  onChange={(e) => setNewText(e.target.value)}
                  placeholder="Ex.: Você praticou atividade física hoje?"
                />
              </label>
              <div className="set-row">
                <label>
                  Tipo
                  <select value={newType} onChange={(e) => setNewType(e.target.value as QuestionType)}>
                    <option value="scale">Escala (0–10 / emoji)</option>
                    <option value="boolean">Sim / Não</option>
                    <option value="choice">Múltipla escolha</option>
                    <option value="integer">Número</option>
                    <option value="free_text">Texto livre</option>
                  </select>
                </label>
                {newType === "choice" ? (
                  <label>
                    Opções (separadas por vírgula)
                    <input value={newChoices} onChange={(e) => setNewChoices(e.target.value)} />
                  </label>
                ) : null}
              </div>
              <div className="set-actions">
                <button className="btn" onClick={addQuestion} disabled={busy || !newText.trim()}>
                  Adicionar
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
