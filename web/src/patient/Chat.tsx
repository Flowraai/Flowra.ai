import { useEffect, useRef, useState, type FormEvent } from "react";
import { PatientApiError, type ChatMessage, type MessageSender } from "./api";

const WHO: Record<MessageSender, string> = { patient: "Você", doctor: "Médico", ai: "Apoio" };

export function Chat({
  title,
  subtitle,
  load,
  send,
  placeholder,
  emptyHint,
}: {
  title: string;
  subtitle: string;
  load: () => Promise<ChatMessage[]>;
  send: (body: string) => Promise<ChatMessage>;
  placeholder: string;
  emptyHint: string;
}) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function refresh() {
    try {
      const list = await load();
      // API devolve do mais novo pro mais antigo — invertemos para cronológico.
      setMessages([...list].reverse());
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Falha ao carregar as mensagens.");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    setError(null);
    setDraft("");
    try {
      await send(body);
      await refresh();
    } catch (err) {
      setError(err instanceof PatientApiError ? err.message : "Não foi possível enviar.");
      setDraft(body);
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
      <h1 className="pt-h1">{title}</h1>
      <div className="pt-sub">{subtitle}</div>

      {messages === null ? (
        <div className="pt-center">
          <div className="pt-spinner" />
        </div>
      ) : messages.length === 0 ? (
        <div className="pt-card pt-muted">{emptyHint}</div>
      ) : (
        <div className="pt-chat">
          {messages.map((m) => (
            <div key={m.id} className={`pt-bubble ${m.sender === "patient" ? "mine" : "theirs"}`}>
              {m.sender !== "patient" ? <div className="who">{WHO[m.sender]}</div> : null}
              {m.body}
            </div>
          ))}
          <div ref={endRef} />
        </div>
      )}

      {error ? <div className="pt-error" style={{ margin: "6px 0" }}>{error}</div> : null}

      <form className="pt-composer" onSubmit={onSend}>
        <input
          className="pt-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
        />
        <button type="submit" disabled={sending || !draft.trim()} aria-label="Enviar">
          ➤
        </button>
      </form>
    </div>
  );
}
