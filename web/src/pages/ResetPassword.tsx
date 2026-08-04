import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { auth } from "../api/endpoints";
import { ApiError } from "../api/client";
import { ThemeToggle } from "../components/ThemeToggle";
import { IconFlower } from "../components/icons";
import "./Login.css";

export function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.resetPassword(token.trim(), password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível redefinir. O link pode ter expirado.");
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
            <span>Redefinir senha</span>
          </div>
        </div>

        {done ? (
          <>
            <h1>Senha redefinida</h1>
            <p className="lede">Sua senha foi atualizada. As outras sessões foram encerradas.</p>
            <button className="btn" type="button" onClick={() => navigate("/login", { replace: true })}>
              Ir para o login
            </button>
          </>
        ) : (
          <>
            <h1>Nova senha</h1>
            <p className="lede">Defina uma nova senha para sua conta.</p>
            {!params.get("token") ? (
              <label>
                Código do e-mail
                <input value={token} onChange={(e) => setToken(e.target.value)} required />
              </label>
            ) : null}
            <label>
              Nova senha
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </label>
            {error ? <div className="login-error">{error}</div> : null}
            <button className="btn" type="submit" disabled={busy || !token.trim()}>
              {busy ? "Redefinindo…" : "Redefinir senha"}
            </button>
            <div className="login-links">
              <button type="button" className="link" onClick={() => navigate("/login")}>
                ← Voltar para entrar
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}
