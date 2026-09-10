// Leitura dos dados de saúde do Android via Health Connect.
// O Health Connect agrega dados de Mi Fitness/Zepp (Mi Band/Xiaomi), Samsung
// Health e Google Fit — então cobrimos as marcas mais comuns no Brasil.

import {
  initialize,
  getSdkStatus,
  requestPermission,
  readRecords,
  SdkAvailabilityStatus,
} from "react-native-health-connect";
import type { WearableDay } from "./api";

const PERMISSIONS = [
  { accessType: "read", recordType: "Steps" },
  { accessType: "read", recordType: "SleepSession" },
  { accessType: "read", recordType: "RestingHeartRate" },
  { accessType: "read", recordType: "HeartRateVariabilityRmssd" },
] as const;

export type HealthAvailability = "ok" | "unavailable" | "update_required";

export async function checkAvailability(): Promise<HealthAvailability> {
  const status = await getSdkStatus();
  if (status === SdkAvailabilityStatus.SDK_AVAILABLE) return "ok";
  if (status === SdkAvailabilityStatus.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED) {
    return "update_required";
  }
  return "unavailable";
}

export async function connectHealth(): Promise<boolean> {
  const ok = await initialize();
  if (!ok) return false;
  const granted = await requestPermission([...PERMISSIONS]);
  return granted.length > 0;
}

function localDay(iso: string): string {
  const d = new Date(iso);
  const off = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - off).toISOString().slice(0, 10);
}

async function safeRead(recordType: string, startTime: string, endTime: string): Promise<any[]> {
  try {
    const res = await readRecords(recordType as never, {
      timeRangeFilter: { operator: "between", startTime, endTime },
    });
    return (res as { records?: unknown[] }).records ?? [];
  } catch {
    return []; // aparelho pode não ter esse tipo de dado
  }
}

/** Lê e agrega os últimos `days` dias em resumos diários. */
export async function readDailyHealth(days = 14): Promise<WearableDay[]> {
  await initialize();
  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);
  const startTime = start.toISOString();
  const endTime = end.toISOString();

  const [steps, sleep, rhr, hrv] = await Promise.all([
    safeRead("Steps", startTime, endTime),
    safeRead("SleepSession", startTime, endTime),
    safeRead("RestingHeartRate", startTime, endTime),
    safeRead("HeartRateVariabilityRmssd", startTime, endTime),
  ]);

  const byDay = new Map<string, { steps: number; sleep: number; rhr: number[]; hrv: number[] }>();
  const bucket = (day: string) => {
    let b = byDay.get(day);
    if (!b) {
      b = { steps: 0, sleep: 0, rhr: [], hrv: [] };
      byDay.set(day, b);
    }
    return b;
  };

  for (const r of steps) {
    if (r?.startTime && typeof r.count === "number") bucket(localDay(r.startTime)).steps += r.count;
  }
  for (const r of sleep) {
    if (r?.startTime && r?.endTime) {
      const mins = Math.round((new Date(r.endTime).getTime() - new Date(r.startTime).getTime()) / 60000);
      if (mins > 0) bucket(localDay(r.endTime)).sleep += mins;
    }
  }
  for (const r of rhr) {
    const bpm = r?.beatsPerMinute;
    if (r?.time && typeof bpm === "number") bucket(localDay(r.time)).rhr.push(bpm);
  }
  for (const r of hrv) {
    const ms = r?.heartRateVariabilityMillis;
    if (r?.time && typeof ms === "number") bucket(localDay(r.time)).hrv.push(ms);
  }

  const avg = (xs: number[]) => (xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null);

  return [...byDay.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, b]) => ({
      day,
      sleep_minutes: b.sleep || null,
      resting_hr: avg(b.rhr),
      hrv_ms: avg(b.hrv),
      steps: b.steps || null,
    }));
}
