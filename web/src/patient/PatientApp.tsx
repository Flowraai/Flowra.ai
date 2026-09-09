import { useEffect, useState } from "react";
import {
  getPatientToken,
  patientApi,
  patientAuth,
  PatientApiError,
  setPatientToken,
  type PatientToday,
} from "./api";
import { PatientAuth } from "./PatientAuth";
import { Today } from "./Today";
import { Checkin } from "./Checkin";
import { Medications } from "./Medications";
import { Chat } from "./Chat";
import { Calendar } from "./Calendar";
import "./patient.css";

type Tab = "today" | "cal" | "meds" | "chat" | "support";

const TABS: { id: Tab; label: string; ico: string }[] = [
  { id: "today", label: "Hoje", ico: "🏠" },
  { id: "cal", label: "Calendário", ico: "🗓️" },
  { id: "meds", label: "Remédios", ico: "💊" },
  { id: "chat", label: "Médico", ico: "💬" },
  { id: "support", label: "Apoio", ico: "💜" },
];

/** Captura ?token=... do link de convite, guarda e limpa a URL. */
function captureTokenFromUrl(): void {
  try {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setPatientToken(token);
      const url = window.location.pathname; // remove o token da barra de endereço
      window.history.replaceState({}, "", url);
    }
  } catch {
    /* ignore */
  }
}

type AuthState = "loading" | "app" | "login" | "activate";

export function PatientApp() {
  const [ready, setReady] = useState(false);
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [authName, setAuthName] = useState<string | undefined>(undefined);
  const [today, setToday] = useState<PatientToday | null>(null);
  const [tab, setTab] = useState<Tab>("today");
  const [checkinOpen, setCheckinOpen] = useState(false);
  const [checkinFor, setCheckinFor] = useState<string | null>(null);
  const [checkinLabel, setCheckinLabel] = useState<string | null>(null);
  const [calKey, setCalKey] = useState(0);
  const [toast, setToast] = useState<string | null>(null);

  function openCheckin(forDate: string | null, label: string | null) {
    setCheckinFor(forDate);
    setCheckinLabel(label);
    setCheckinOpen(true);
  }

  async function loadToday() {
    try {
      const data = await patientApi.today();
      setToday(data);
      setAuthState("app");
    } catch {
      // erro de rede — mantém sessão, mostra o app (vazio até recarregar)
      setAuthState("app");
    } finally {
      setReady(true);
    }
  }

  // Decide a tela inicial: app (ativado), criar acesso (token válido não ativado)
  // ou entrar (sem token / token inválido).
  async function boot() {
    if (!getPatientToken()) {
      setAuthState("login");
      setReady(true);
      return;
    }
    try {
      const acc = await patientAuth.account();
      setAuthName(acc.name);
      if (acc.activated) {
        await loadToday();
      } else {
        setAuthState("activate");
        setReady(true);
      }
    } catch (e) {
      // 401 → token inválido/expirado: já foi limpo pela api; vai para login.
      if (e instanceof PatientApiError && e.status === 401) setAuthState("login");
      else setAuthState("app"); // erro de rede — tenta seguir com a sessão
      setReady(true);
    }
  }

  // Chamado após ativar/entrar/redefinir: guarda o token de sessão e abre o app.
  async function onAuthed(token: string) {
    setPatientToken(token);
    setReady(false);
    await loadToday();
    setReady(true);
  }

  useEffect(() => {
    captureTokenFromUrl();
    boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!ready) {
    return (
      <div className="pt-app">
        <div className="pt-center">
          <div className="pt-spinner" />
        </div>
      </div>
    );
  }

  if (authState === "login" || authState === "activate") {
    return (
      <div className="pt-app">
        <PatientAuth initialMode={authState} patientName={authName} onAuthed={onAuthed} />
      </div>
    );
  }

  async function onCheckinDone(msg: string) {
    setCheckinOpen(false);
    setCheckinFor(null);
    setCheckinLabel(null);
    setCalKey((k) => k + 1); // recarrega o calendário
    setToast(msg);
    await loadToday();
    setTimeout(() => setToast(null), 4000);
  }

  return (
    <div className="pt-app">
      <div className="pt-shell">
        <div className="pt-top">
          <div className="pt-mark">✿</div>
          <div>
            <b>Flowra Care</b>
            <span>Seu acompanhamento</span>
          </div>
        </div>

        <div className="pt-body">
          {checkinOpen ? (
            <Checkin
              onDone={onCheckinDone}
              onCancel={() => setCheckinOpen(false)}
              forDate={checkinFor ?? undefined}
              dateLabel={checkinLabel ?? undefined}
            />
          ) : (
            <>
              {toast ? <div className="pt-done" style={{ marginBottom: 14 }}>{toast}</div> : null}
              {tab === "today" && today ? (
                <Today today={today} onStartCheckin={() => openCheckin(null, null)} />
              ) : null}
              {tab === "cal" ? (
                <Calendar
                  key={calKey}
                  onPick={(iso, label) => openCheckin(iso || null, iso ? label : null)}
                />
              ) : null}
              {tab === "meds" ? <Medications /> : null}
              {tab === "chat" ? (
                <Chat
                  title="Falar com o médico"
                  subtitle="Mensagens para a sua equipe de cuidado."
                  load={patientApi.messages}
                  send={patientApi.sendMessage}
                  placeholder="Escreva uma mensagem…"
                  emptyHint="Envie uma mensagem para o seu médico quando precisar."
                />
              ) : null}
              {tab === "support" ? (
                <Chat
                  title="Apoio"
                  subtitle="Converse com o apoio do Flowra. Em caso de risco, seu médico é avisado."
                  load={patientApi.aiHistory}
                  send={patientApi.sendAi}
                  placeholder="Como você está se sentindo?"
                  emptyHint="Este espaço é para desabafar e receber apoio a qualquer hora."
                />
              ) : null}
            </>
          )}
        </div>

        {!checkinOpen ? (
          <nav className="pt-tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={`pt-tab ${tab === t.id ? "on" : ""}`}
                onClick={() => setTab(t.id)}
              >
                <span className="ico">{t.ico}</span>
                {t.label}
              </button>
            ))}
          </nav>
        ) : null}
      </div>
    </div>
  );
}
