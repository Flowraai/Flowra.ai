import { useEffect, useState } from "react";
import { Linking, Pressable, ScrollView, Text, View } from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Appointment, Exam, Prescription } from "../api/types";
import { Card, ErrorView, Loading, text } from "../components/ui";
import { useTheme, type Theme } from "../theme";

const KIND: Record<string, string> = { consultation: "Consulta", return: "Retorno" };

function fmt(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AgendaScreen() {
  const { theme } = useTheme();
  const t = text(theme);
  const [appts, setAppts] = useState<Appointment[] | null>(null);
  const [exams, setExams] = useState<Exam[] | null>(null);
  const [rx, setRx] = useState<Prescription[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([patientApi.appointments(), patientApi.exams(), patientApi.prescriptions()])
      .then(([a, e, p]) => {
        setAppts(a);
        setExams(e);
        setRx(p);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Falha ao carregar."));
  }
  useEffect(load, []);

  async function confirm(a: Appointment) {
    setBusy(a.id);
    try {
      const updated = await patientApi.confirmAppointment(a.id);
      setAppts((prev) => (prev ? prev.map((x) => (x.id === a.id ? updated : x)) : prev));
    } catch {
      /* mantém */
    } finally {
      setBusy(null);
    }
  }

  if (error) return <ErrorView message={error} onRetry={load} />;
  if (!appts || !exams || !rx) return <Loading label="Carregando…" />;

  return (
    <ScrollView contentContainerStyle={{ padding: 20, gap: 22 }}>
      <View>
        <Text style={[t.h2, { marginBottom: 10 }]}>Próximas consultas</Text>
        {appts.length === 0 ? (
          <Card>
            <Text style={t.muted}>Nenhuma consulta agendada. 📅</Text>
          </Card>
        ) : (
          <View style={{ gap: 10 }}>
            {appts.map((a) => (
              <Card key={a.id}>
                <Text style={{ color: theme.ink, fontSize: 15.5, fontWeight: "700" }}>{fmt(a.scheduled_at)}</Text>
                <Text style={t.muted}>
                  {KIND[a.kind] ?? "Consulta"}
                  {a.location ? ` · ${a.location}` : ""}
                </Text>
                {a.status === "confirmed" ? (
                  <Text style={{ color: theme.green, fontWeight: "700", marginTop: 8 }}>✓ Presença confirmada</Text>
                ) : (
                  <Pressable
                    onPress={() => confirm(a)}
                    disabled={busy === a.id}
                    style={{
                      marginTop: 10,
                      backgroundColor: theme.accent,
                      borderRadius: 12,
                      paddingVertical: 11,
                      alignItems: "center",
                    }}
                  >
                    <Text style={{ color: theme.onAccent, fontWeight: "700" }}>Confirmar presença</Text>
                  </Pressable>
                )}
              </Card>
            ))}
          </View>
        )}
      </View>

      <View>
        <Text style={[t.h2, { marginBottom: 10 }]}>Exames</Text>
        {exams.length === 0 ? (
          <Card>
            <Text style={t.muted}>Nenhum exame solicitado.</Text>
          </Card>
        ) : (
          <View style={{ gap: 10 }}>
            {exams.map((ex) => (
              <Card key={ex.id}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <Text style={{ color: theme.ink, fontSize: 15, fontWeight: "700", flex: 1 }}>{ex.name}</Text>
                  <StatusPill
                    theme={theme}
                    label={ex.status === "available" ? "Disponível" : "Solicitado"}
                    color={ex.status === "available" ? theme.green : theme.muted}
                  />
                </View>
                {ex.notes ? <Text style={[t.muted, { marginTop: 4 }]}>{ex.notes}</Text> : null}
                {ex.status === "available" && ex.result_url ? (
                  <Pressable onPress={() => Linking.openURL(ex.result_url!)} style={{ marginTop: 8 }}>
                    <Text style={{ color: theme.accentInk, fontWeight: "700" }}>Ver resultado →</Text>
                  </Pressable>
                ) : null}
              </Card>
            ))}
          </View>
        )}
      </View>

      <View>
        <Text style={[t.h2, { marginBottom: 10 }]}>Receitas</Text>
        {rx.length === 0 ? (
          <Card>
            <Text style={t.muted}>Nenhuma receita disponível.</Text>
          </Card>
        ) : (
          <View style={{ gap: 10 }}>
            {rx.map((p) => (
              <Card key={p.id}>
                {(p.items ?? []).map((it, i) => (
                  <Text key={i} style={{ color: theme.ink, fontSize: 14.5, marginBottom: 2 }}>
                    • <Text style={{ fontWeight: "700" }}>{it.name}</Text> {it.dose}
                    {it.instructions ? ` — ${it.instructions}` : ""}
                  </Text>
                ))}
                <Text style={[t.muted, { marginTop: 4, fontSize: 12 }]}>
                  {p.issued_at ? `Emitida em ${new Date(p.issued_at).toLocaleDateString("pt-BR")}` : ""}
                </Text>
                {p.pdf_url ? (
                  <Pressable onPress={() => Linking.openURL(p.pdf_url!)} style={{ marginTop: 6 }}>
                    <Text style={{ color: theme.accentInk, fontWeight: "700" }}>Abrir PDF →</Text>
                  </Pressable>
                ) : null}
              </Card>
            ))}
          </View>
        )}
      </View>
    </ScrollView>
  );
}

function StatusPill({ theme, label, color }: { theme: Theme; label: string; color: string }) {
  return (
    <Text
      style={{
        color,
        fontSize: 11.5,
        fontWeight: "700",
        backgroundColor: theme.surface2,
        borderRadius: 999,
        paddingHorizontal: 9,
        paddingVertical: 3,
        overflow: "hidden",
      }}
    >
      {label}
    </Text>
  );
}
