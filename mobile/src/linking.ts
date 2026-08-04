// Deep link: extrai o código de acesso de uma URL (?token=... em qualquer esquema).
// Funciona com o esquema do app (flowracare://acesso?token=...) e com o link web
// do médico quando aberto no app (universal/app links configurados no deploy).

import * as Linking from "expo-linking";

export function tokenFromUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = Linking.parse(url);
    const t = parsed.queryParams?.token;
    const value = Array.isArray(t) ? t[0] : t;
    if (typeof value === "string" && value.trim()) return value.trim();
  } catch {
    /* ignore */
  }
  return null;
}

/** Aceita tanto um código puro quanto um link colado (extrai o token deste). */
export function tokenFromInput(raw: string): string {
  const trimmed = raw.trim();
  if (trimmed.includes("token=") || trimmed.includes("://")) {
    return tokenFromUrl(trimmed) ?? trimmed;
  }
  return trimmed;
}
