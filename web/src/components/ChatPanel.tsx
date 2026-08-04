import { useEffect, useRef, useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import { IconChat, IconSend } from "./icons";
import type { ChatMessage } from "../api/types";
import "./ChatPanel.css";

export function ChatPanel({ patientId }: { patientId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    patients
      .messages(patientId)
      .then((m) => active && setMessages([...m].reverse())) // API devolve desc; exibimos asc
      .catch((e) => active && setError(e instanceof ApiError ? e.message : "Falha ao carregar a conversa."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [patientId]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [messages]);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      const msg = await patients.sendMessage(patientId, text);
      setMessages((prev) => [...prev, msg]);
      setDraft("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível enviar.");
    } finally {
      setSending(false);
    }
  }

  const unread = messages.filter((m) => m.sender === "patient" && !m.read_at).length;

  return (
    <div className="card chat">
      <div className="hd">
        <IconChat width={16} height={16} color="var(--accent)" />
        <h4>Conversa com o paciente</h4>
        {unread > 0 ? <span className="tag">{unread} não lida(s)</span> : null}
      </div>
      <div className="chat-bd" ref={bodyRef}>
        {loading ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : error ? (
          <div className="state">
            <span className="err">{error}</span>
          </div>
        ) : messages.length === 0 ? (
          <div className="state">Nenhuma mensagem ainda. Escreva a primeira.</div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`msg ${m.sender === "doctor" ? "me" : "them"}`}>
              {m.sender === "ai" ? <span className="who-ai">IA</span> : null}
              {m.body}
              <span className="t">
                {new Date(m.created_at).toLocaleString("pt-BR", {
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
                {m.sender === "doctor" && m.read_at ? " · lida" : ""}
              </span>
            </div>
          ))
        )}
      </div>
      <form className="compose" onSubmit={onSend}>
        <input
          className="box"
          placeholder="Escreva uma mensagem…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="Mensagem"
        />
        <button className="send" type="submit" disabled={sending || !draft.trim()} aria-label="Enviar">
          <IconSend width={17} height={17} color="#fff" />
        </button>
      </form>
    </div>
  );
}
