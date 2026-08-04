import { useEffect, useState } from "react";
import { ApiError } from "../api/client";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/** Executa um fetch quando as `deps` mudam. `fn` deve ser estável quanto às deps. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });

  useEffect(() => {
    let active = true;
    setState({ data: null, loading: true, error: null });
    fn()
      .then((data) => active && setState({ data, loading: false, error: null }))
      .catch((e) => {
        if (!active) return;
        const msg = e instanceof ApiError ? e.message : "Falha ao carregar. Tente novamente.";
        setState({ data: null, loading: false, error: msg });
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
