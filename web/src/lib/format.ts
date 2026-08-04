import type { RiskLevel } from "../api/types";

export const RISK_LABEL: Record<RiskLevel, string> = {
  green: "Estável",
  yellow: "Atenção",
  orange: "Acompanhar",
  red: "Urgente",
};

export const RISK_ORDER: Record<RiskLevel, number> = { green: 0, yellow: 1, orange: 2, red: 3 };

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

export function avatarGradient(risk: RiskLevel): string {
  const map: Record<RiskLevel, [string, string]> = {
    green: ["#2e9e6b", "#1f7d53"],
    yellow: ["#b9890a", "#8f6a07"],
    orange: ["#da7429", "#b45a18"],
    red: ["#d3423a", "#a83029"],
  };
  const [a, b] = map[risk];
  return `linear-gradient(135deg, ${a}, ${b})`;
}

/** Data relativa curta em pt-BR ("há 3 dias", "ontem", "hoje 09h"). */
export function relativeDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dayDiff = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
  const hh = String(d.getHours()).padStart(2, "0");
  if (dayDiff <= 0) return `hoje ${hh}h`;
  if (dayDiff === 1) return `ontem ${hh}h`;
  if (dayDiff < 7) return `há ${dayDiff} dias`;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function shortDay(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dayDiff = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
  if (dayDiff === 0) return "Hoje";
  if (dayDiff === 1) return "Ontem";
  return d.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "");
}

/** Formata centavos como moeda em pt-BR (14990 -> "R$ 149,90"). */
export function money(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** Lê um número de uma resposta estruturada (que pode vir como string). */
export function num(value: unknown): number | null {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const n = Number(value.replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
