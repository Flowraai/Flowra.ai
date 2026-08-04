import { useEffect, useState } from "react";
import { effectiveTheme, getThemePref, setThemePref, type ThemePref } from "../lib/theme";

export function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>(getThemePref());

  useEffect(() => {
    // Se estiver em "sistema", reage à mudança do SO.
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => pref === "system" && setPref("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [pref]);

  const active = effectiveTheme(pref);
  function choose(next: "light" | "dark") {
    setThemePref(next);
    setPref(next);
  }

  return (
    <div className="theme-toggle" role="group" aria-label="Tema">
      <button
        aria-label="Tema claro"
        aria-pressed={active === "light"}
        className={active === "light" ? "on" : ""}
        onClick={() => choose("light")}
      >
        ☀
      </button>
      <button
        aria-label="Tema escuro"
        aria-pressed={active === "dark"}
        className={active === "dark" ? "on" : ""}
        onClick={() => choose("dark")}
      >
        ☾
      </button>
    </div>
  );
}
