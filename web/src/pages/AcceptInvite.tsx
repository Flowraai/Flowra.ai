import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { ThemeToggle } from "../components/ThemeToggle";
import { IconFlower } from "../components/icons";
import "./Login.css";

export function AcceptInvite() {
  const { acceptInvite } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await acceptInvite(token, name.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível aceitar o convite.");
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
            <span>Convite para a equipe</span>
          </div>
        </div>

        <h1>Aceitar convite</h1>
        <p className="lede">Defina seu nome e senha para acessar a clínica.</p>

        {!token ? (
          <div className="login-error">Link de convite inválido (sem token).</div>
        ) : null}

        <label>
          Nome
          <input value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
        </label>
        <label>
          Senha
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
        </label>

        {error ? <div className="login-error">{error}</div> : null}

        <button className="btn" type="submit" disabled={busy || !token}>
          {busy ? "Entrando…" : "Aceitar e entrar"}
        </button>
      </form>
    </div>
  );
}
