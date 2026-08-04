import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { ThemeToggle } from "../components/ThemeToggle";
import { IconFlower } from "../components/icons";
import "./Login.css";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível entrar. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

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

        <h1>Entrar</h1>
        <p className="lede">Acesse o acompanhamento dos seus pacientes.</p>

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
        <label>
          Senha
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error ? <div className="login-error">{error}</div> : null}

        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
        <p className="foot muted">
          A IA do Flowra apoia a priorização de casos — não substitui o julgamento clínico.
        </p>
      </form>
    </div>
  );
}
