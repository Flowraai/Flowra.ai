import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { auth } from "../api/endpoints";
import { ThemeToggle } from "../components/ThemeToggle";
import { IconFlower } from "../components/icons";
import "./Login.css";

type Mode = "login" | "register" | "forgot";

export function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function switchMode(m: Mode) {
    setMode(m);
    setError(null);
    setInfo(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
        navigate("/", { replace: true });
      } else if (mode === "register") {
        await register(email, password, name);
        navigate("/", { replace: true });
      } else {
        await auth.forgotPassword(email);
        setInfo("Se o e-mail existir, enviamos as instruções de redefinição.");
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : mode === "register"
            ? "Não foi possível criar a conta."
            : "Não foi possível entrar. Tente novamente.",
      );
    } finally {
      setBusy(false);
    }
  }

  const title = mode === "login" ? "Entrar" : mode === "register" ? "Criar conta" : "Recuperar acesso";
  const cta = mode === "login" ? "Entrar" : mode === "register" ? "Criar conta" : "Enviar instruções";

  return (
    <div className="login">
      <div className="login-top">
        <ThemeToggle />
      </div>
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-brand">
          <div className="mark">
            <IconFlower width={20} height={20} color="#fff" />
          </div>
          <div>
            <b>Flowra Care</b>
            <span>Painel do médico</span>
          </div>
        </div>

        <h1>{title}</h1>
        <p className="lede">
          {mode === "login"
            ? "Acesse o acompanhamento dos seus pacientes."
            : mode === "register"
              ? "Crie sua conta para começar a acompanhar pacientes."
              : "Informe seu e-mail para redefinir a senha."}
        </p>

        {mode === "register" ? (
          <label>
            Nome
            <input value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
          </label>
        ) : null}

        <label>
          E-mail
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        {mode !== "forgot" ? (
          <label>
            Senha
            <input
              type="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>
        ) : null}

        {error ? <div className="login-error">{error}</div> : null}
        {info ? <div className="login-info">{info}</div> : null}

        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Aguarde…" : cta}
        </button>

        <div className="login-links">
          {mode === "login" ? (
            <>
              <button type="button" className="link" onClick={() => switchMode("forgot")}>
                Esqueci a senha
              </button>
              <button type="button" className="link" onClick={() => switchMode("register")}>
                Criar conta
              </button>
            </>
          ) : (
            <button type="button" className="link" onClick={() => switchMode("login")}>
              ← Voltar para entrar
            </button>
          )}
        </div>

        <p className="foot muted">
          A IA do Flowra apoia a priorização de casos — não substitui o julgamento clínico.
        </p>
      </form>
    </div>
  );
}
