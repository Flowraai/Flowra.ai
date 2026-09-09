import { useState } from "react";
import { patientAuth, PatientApiError } from "./api";

type Mode = "login" | "activate" | "forgot" | "reset";

// Máscara leve de CPF (000.000.000-00) só para exibição; enviamos os dígitos.
function maskCpf(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 11);
  return d
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

export function PatientAuth({
  initialMode,
  patientName,
  onAuthed,
}: {
  initialMode: "login" | "activate";
  patientName?: string;
  onAuthed: (token: string) => void;
}) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [cpf, setCpf] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const cpfDigits = cpf.replace(/\D/g, "");

  function fail(e: unknown, fallback: string) {
    setError(e instanceof PatientApiError ? e.message : fallback);
  }

  async function doActivate() {
    if (cpfDigits.length !== 11 || password.length < 6) return;
    setBusy(true);
    setError(null);
    try {
      const s = await patientAuth.activate(cpfDigits, password);
      onAuthed(s.access_token);
    } catch (e) {
      fail(e, "Não foi possível criar o acesso.");
    } finally {
      setBusy(false);
    }
  }

  async function doLogin() {
    if (cpfDigits.length !== 11 || !password) return;
    setBusy(true);
    setError(null);
    try {
      const s = await patientAuth.login(cpfDigits, password);
      onAuthed(s.access_token);
    } catch (e) {
      fail(e, "Não foi possível entrar.");
    } finally {
      setBusy(false);
    }
  }

  async function doForgot() {
    if (cpfDigits.length !== 11) return;
    setBusy(true);
    setError(null);
    try {
      const r = await patientAuth.forgot(cpfDigits);
      setInfo(r.message);
      setMode("reset");
    } catch (e) {
      fail(e, "Não foi possível enviar o código.");
    } finally {
      setBusy(false);
    }
  }

  async function doReset() {
    if (cpfDigits.length !== 11 || code.trim().length < 4 || newPassword.length < 6) return;
    setBusy(true);
    setError(null);
    try {
      const s = await patientAuth.reset(cpfDigits, code.trim(), newPassword);
      onAuthed(s.access_token);
    } catch (e) {
      fail(e, "Não foi possível redefinir a senha.");
    } finally {
      setBusy(false);
    }
  }

  const cpfField = (
    <input
      className="pt-input"
      value={maskCpf(cpf)}
      onChange={(e) => setCpf(e.target.value)}
      placeholder="CPF"
      inputMode="numeric"
      autoComplete="username"
    />
  );

  return (
    <div className="pt-shell">
      <div className="pt-top">
        <div className="pt-mark">✿</div>
        <div>
          <b>Flowra Care</b>
          <span>Acompanhamento do paciente</span>
        </div>
      </div>
      <div className="pt-center" style={{ flexDirection: "column", gap: 16 }}>
        <div className="pt-mark" style={{ width: 54, height: 54, fontSize: 26, borderRadius: 16 }}>
          ✿
        </div>

        {mode === "activate" ? (
          <>
            <div>
              <h1 className="pt-h1">Criar seu acesso</h1>
              <p className="pt-sub" style={{ marginBottom: 0 }}>
                {patientName ? `Olá, ${patientName.split(" ")[0]}! ` : ""}
                Defina seu CPF e uma senha para entrar sempre que quiser.
              </p>
            </div>
            <div className="pt-card" style={{ width: "100%", textAlign: "left" }}>
              {cpfField}
              <input
                className="pt-input"
                style={{ marginTop: 10 }}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Crie uma senha (mín. 6 caracteres)"
                autoComplete="new-password"
              />
              {error ? <div className="pt-error" style={{ marginTop: 10 }}>{error}</div> : null}
              <button
                className="pt-btn"
                style={{ marginTop: 10 }}
                onClick={doActivate}
                disabled={busy || cpfDigits.length !== 11 || password.length < 6}
              >
                {busy ? "Criando…" : "Criar acesso e entrar"}
              </button>
            </div>
          </>
        ) : mode === "login" ? (
          <>
            <div>
              <h1 className="pt-h1">Entrar</h1>
              <p className="pt-sub" style={{ marginBottom: 0 }}>Acesse com seu CPF e senha.</p>
            </div>
            <div className="pt-card" style={{ width: "100%", textAlign: "left" }}>
              {cpfField}
              <input
                className="pt-input"
                style={{ marginTop: 10 }}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Senha"
                autoComplete="current-password"
                onKeyDown={(e) => e.key === "Enter" && doLogin()}
              />
              {error ? <div className="pt-error" style={{ marginTop: 10 }}>{error}</div> : null}
              <button
                className="pt-btn"
                style={{ marginTop: 10 }}
                onClick={doLogin}
                disabled={busy || cpfDigits.length !== 11 || !password}
              >
                {busy ? "Entrando…" : "Entrar"}
              </button>
              <button
                className="pt-link"
                style={{ marginTop: 12, background: "none", border: 0 }}
                onClick={() => {
                  setError(null);
                  setInfo(null);
                  setMode("forgot");
                }}
              >
                Esqueci minha senha
              </button>
            </div>
          </>
        ) : mode === "forgot" ? (
          <>
            <div>
              <h1 className="pt-h1">Recuperar senha</h1>
              <p className="pt-sub" style={{ marginBottom: 0 }}>
                Informe seu CPF. Enviaremos um código ao seu WhatsApp/e-mail cadastrado.
              </p>
            </div>
            <div className="pt-card" style={{ width: "100%", textAlign: "left" }}>
              {cpfField}
              {error ? <div className="pt-error" style={{ marginTop: 10 }}>{error}</div> : null}
              <button
                className="pt-btn"
                style={{ marginTop: 10 }}
                onClick={doForgot}
                disabled={busy || cpfDigits.length !== 11}
              >
                {busy ? "Enviando…" : "Enviar código"}
              </button>
              <button
                className="pt-link"
                style={{ marginTop: 12, background: "none", border: 0 }}
                onClick={() => {
                  setError(null);
                  setMode("login");
                }}
              >
                Voltar para entrar
              </button>
            </div>
          </>
        ) : (
          <>
            <div>
              <h1 className="pt-h1">Redefinir senha</h1>
              <p className="pt-sub" style={{ marginBottom: 0 }}>
                {info ?? "Digite o código que você recebeu e crie uma nova senha."}
              </p>
            </div>
            <div className="pt-card" style={{ width: "100%", textAlign: "left" }}>
              {cpfField}
              <input
                className="pt-input"
                style={{ marginTop: 10 }}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Código recebido"
                inputMode="numeric"
              />
              <input
                className="pt-input"
                style={{ marginTop: 10 }}
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Nova senha (mín. 6 caracteres)"
                autoComplete="new-password"
              />
              {error ? <div className="pt-error" style={{ marginTop: 10 }}>{error}</div> : null}
              <button
                className="pt-btn"
                style={{ marginTop: 10 }}
                onClick={doReset}
                disabled={busy || cpfDigits.length !== 11 || code.trim().length < 4 || newPassword.length < 6}
              >
                {busy ? "Salvando…" : "Redefinir e entrar"}
              </button>
              <button
                className="pt-link"
                style={{ marginTop: 12, background: "none", border: 0 }}
                onClick={() => {
                  setError(null);
                  setMode("login");
                }}
              >
                Voltar para entrar
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
