import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { auth, clinic } from "../api/endpoints";
import { getToken, setToken } from "../api/client";
import type { DoctorProfile, SessionInfo } from "../api/types";

interface AuthState {
  session: SessionInfo | null;
  doctor: DoctorProfile | null;   // derivado da sessão (null para recepção)
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, specialty?: string) => Promise<void>;
  acceptInvite: (token: string, name: string, password: string) => Promise<void>;
  refresh: () => Promise<void>;
  logout: () => void;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const s = await auth.session();
        if (active) setSession(s);
      } catch {
        if (active) setToken(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      session,
      doctor: session?.doctor ?? null,
      loading,
      async login(email, password) {
        const pair = await auth.login(email, password);
        setToken(pair.access_token);
        setSession(await auth.session());
      },
      async register(email, password, name, specialty) {
        const pair = await auth.register(email, password, name, specialty);
        setToken(pair.access_token);
        setSession(await auth.session());
      },
      async acceptInvite(token, name, password) {
        const pair = await clinic.accept({ token, name, password });
        setToken(pair.access_token);
        setSession(await auth.session());
      },
      async refresh() {
        setSession(await auth.session());
      },
      logout() {
        setToken(null);
        setSession(null);
      },
    }),
    [session, loading],
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return ctx;
}
