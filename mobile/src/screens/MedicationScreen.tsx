import { useEffect, useState } from "react";
import { ScrollView, Text, Pressable, View } from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { IntakeStatus, MedicationDose } from "../api/types";
import { Card, ErrorView, Loading, text } from "../components/ui";
import { useTheme, type Theme } from "../theme";

const RESP: { status: IntakeStatus; label: string; emoji: string }[] = [
  { status: "taken", label: "Tomei", emoji: "✓" },
  { status: "later", label: "Depois", emoji: "⏰" },
  { status: "missed", label: "Não tomei", emoji: "✕" },
];

function hhmm(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function MedicationScreen() {
  const { theme } = useTheme();
  const t = text(theme);
  const [doses, setDoses] = useState<MedicationDose[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  function load() {
    setError(null);
    patientApi
      .medicationsToday()
      .then(setDoses)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar."));
  }
  useEffect(load, []);

  async function respond(intakeId: string, status: IntakeStatus) {
    setSaving(intakeId);
    try {
      await patientApi.respondDose(intakeId, status);
      setDoses((prev) => (prev ? prev.map((d) => (d.intake_id === intakeId ? { ...d, status } : d)) : prev));
    } catch {
      /* mantém o estado anterior */
    } finally {
      setSaving(null);
    }
  }

  if (error) return <ErrorView message={error} onRetry={load} />;
  if (!doses) return <Loading label="Carregando…" />;

  return (
    <ScrollView contentContainerStyle={{ padding: 20, gap: 14 }}>
      <Text style={t.h1}>Medicação de hoje</Text>
      {doses.length === 0 ? (
        <Card>
          <Text style={t.muted}>Nenhum lembrete de medicação para hoje. 💊</Text>
        </Card>
      ) : (
        doses.map((d) => (
          <Card key={d.intake_id}>
            <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 12 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ color: theme.ink, fontSize: 16, fontWeight: "700" }}>{d.name}</Text>
                <Text style={t.muted}>
                  {d.dose} · {hhmm(d.scheduled_for)}
                </Text>
              </View>
              <StatusTag status={d.status} theme={theme} />
            </View>
            <View style={{ flexDirection: "row", gap: 8 }}>
              {RESP.map((r) => {
                const on = d.status === r.status;
                return (
                  <Pressable
                    key={r.status}
                    onPress={() => respond(d.intake_id, r.status)}
                    disabled={saving === d.intake_id}
                    style={{
                      flex: 1,
                      backgroundColor: on ? theme.accent : theme.surface2,
                      borderColor: on ? theme.accent : theme.line,
                      borderWidth: 1,
                      borderRadius: 12,
                      paddingVertical: 12,
                      alignItems: "center",
                    }}
                  >
                    <Text style={{ color: on ? theme.onAccent : theme.ink, fontWeight: "700" }}>
                      {r.emoji} {r.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </Card>
        ))
      )}
    </ScrollView>
  );
}

function StatusTag({ status, theme }: { status: IntakeStatus; theme: Theme }) {
  const map: Record<IntakeStatus, { label: string; color: string }> = {
    pending: { label: "Pendente", color: theme.muted },
    taken: { label: "Tomado", color: theme.green },
    later: { label: "Adiado", color: theme.yellow },
    missed: { label: "Não tomado", color: theme.red },
  };
  const s = map[status];
  return (
    <Text style={{ color: s.color, fontWeight: "700", fontSize: 12.5 }}>{s.label}</Text>
  );
}
