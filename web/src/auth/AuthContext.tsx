import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { auth } from "../api/endpoints";
import { getToken, setToken } from "../api/client";
import type { DoctorProfile } from "../api/types";

interface AuthState {
  doctor: DoctorProfile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [doctor, setDoctor] = useState<DoctorProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await auth.me();
        if (active) setDoctor(me);
      } catch {
        setToken(null);
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
      doctor,
      loading,
      async login(email, password) {
        const pair = await auth.login(email, password);
        setToken(pair.access_token);
        setDoctor(await auth.me());
      },
      logout() {
        setToken(null);
        setDoctor(null);
      },
    }),
    [doctor, loading],
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de <AuthProvider>");
  return ctx;
}
