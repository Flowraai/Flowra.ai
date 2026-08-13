import { useCallback, useEffect, useState } from "react";
import { patientApi, PatientApiError, type CalendarDay } from "./api";

const WEEKDAYS = ["D", "S", "T", "Q", "Q", "S", "S"];
const MONTHS = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

function moodEmoji(mood: number | null): string {
  if (mood === null) return "";
  if (mood <= 2) return "😣";
  if (mood <= 4) return "😟";
  if (mood === 5) return "😐";
  if (mood <= 7) return "🙂";
  return "😄";
}

function longLabel(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  return `${d} de ${MONTHS[m - 1]}`;
}

export function Calendar({ onPick }: { onPick: (iso: string, label: string) => void }) {
  const [days, setDays] = useState<Record<string, CalendarDay> | null>(null);
  const [todayIso, setTodayIso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await patientApi.calendar(42);
      const map: Record<string, CalendarDay> = {};
      let today: string | null = null;
      for (const d of list) {
        map[d.date] = d;
        if (d.is_today) today = d.date;
      }
      setDays(map);
      setTodayIso(today ?? list[list.length - 1]?.date ?? null);
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Falha ao carregar o calendário.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <div className="pt-card pt-error">{error}</div>;
  if (!days || !todayIso) {
    return (
      <div className="pt-center">
        <div className="pt-spinner" />
      </div>
    );
  }

  const [ty, tm] = todayIso.split("-").map(Number);
  const first = new Date(ty, tm - 1, 1);
  const daysInMonth = new Date(ty, tm, 0).getDate();
  const leading = first.getDay(); // 0 = domingo
  const cells: (string | null)[] = [];
  for (let i = 0; i < leading; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(`${ty}-${String(tm).padStart(2, "0")}-${String(d).padStart(2, "0")}`);
  }

  return (
    <div>
      <h1 className="pt-h1">Meu calendário</h1>
      <div className="pt-sub">
        Toque num dia em branco (dos últimos dias) para responder um check-in que faltou.
      </div>

      <div className="pt-card">
        <div className="cal-month">
          {MONTHS[tm - 1]} de {ty}
        </div>
        <div className="cal-grid cal-weekdays">
          {WEEKDAYS.map((w, i) => (
            <div key={i} className="cal-wd">
              {w}
            </div>
          ))}
        </div>
        <div className="cal-grid">
          {cells.map((iso, idx) => {
            if (iso === null) return <div key={`b${idx}`} className="cal-cell empty" />;
            const info = days[iso];
            const dayNum = Number(iso.split("-")[2]);
            const done = info?.checked_in;
            const canFill = info?.can_fill;
            const isToday = info?.is_today;
            const clickable = canFill || (isToday && !done);
            return (
              <button
                key={iso}
                type="button"
                className={`cal-cell${done ? " done" : ""}${isToday ? " today" : ""}${
                  canFill ? " fill" : ""
                }`}
                disabled={!clickable}
                onClick={() =>
                  clickable && onPick(isToday && !canFill ? "" : iso, longLabel(iso))
                }
              >
                {done ? (
                  <span className="cal-emoji">{moodEmoji(info.mood) || "✓"}</span>
                ) : (
                  <span className="cal-num">{dayNum}</span>
                )}
                {canFill ? <span className="cal-plus">+</span> : null}
              </button>
            );
          })}
        </div>
        <div className="cal-legend">
          <span>😊 respondido</span>
          <span className="dot-fill">+ responder</span>
          <span className="dot-today">hoje</span>
        </div>
      </div>
    </div>
  );
}
