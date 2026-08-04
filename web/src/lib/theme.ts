// Tema: claro | escuro | sistema (padrão), persistido em localStorage.

export type ThemePref = "light" | "dark" | "system";

const KEY = "flowra-theme";

export function getThemePref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    /* ignore */
  }
  return "system";
}

export function setThemePref(pref: ThemePref): void {
  try {
    if (pref === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch {
    /* ignore */
  }
  applyTheme(pref);
}

export function applyTheme(pref: ThemePref): void {
  const root = document.documentElement;
  if (pref === "light" || pref === "dark") root.setAttribute("data-theme", pref);
  else root.removeAttribute("data-theme");
}

export function effectiveTheme(pref: ThemePref): "light" | "dark" {
  if (pref === "light" || pref === "dark") return pref;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
