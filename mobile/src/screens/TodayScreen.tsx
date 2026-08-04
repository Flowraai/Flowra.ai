import { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { PatientToday } from "../api/types";
import { Button, Card, ErrorView, Loading, text } from "../components/ui";
import { useTheme } from "../theme";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

export function TodayScreen({ onOpenCheckin, nonce }: { onOpenCheckin: () => void; nonce: number }) {
  const { theme } = useTheme();
  const t = text(theme);
  const [data, setData] = useState<PatientToday | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
    patientApi
      .today()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar."))
      .finally(() => setLoading(false));
  }

  useEffect(load, [nonce]);

  if (loading) return <Loading label="Carregando…" />;
  if (error) return <ErrorView message={error} onRetry={load} />;

  const done = data?.checked_in_today;
  const firstName = (data?.patient_name ?? "").split(" ")[0];

  return (
    <ScrollView contentContainerStyle={{ padding: 20, gap: 18 }}>
      <View style={{ gap: 4 }}>
        <Text style={t.muted}>{greeting()},</Text>
        <Text style={t.h1}>{firstName || "tudo bem?"}</Text>
      </View>

      <Card>
        {done ? (
          <View style={{ gap: 8 }}>
            <Text style={{ fontSize: 34 }}>✅</Text>
            <Text style={t.h2}>Check-in de hoje feito</Text>
            <Text style={t.muted}>
              Obrigado por responder hoje. Seu médico acompanha tudo. Volte amanhã. 💚
            </Text>
          </View>
        ) : (
          <View style={{ gap: 12 }}>
            <Text style={{ fontSize: 34 }}>📝</Text>
            <Text style={t.h2}>Como você está hoje?</Text>
            <Text style={t.muted}>Um check-in rápido, menos de 1 minuto. Ajuda seu médico a te acompanhar.</Text>
            <Button label="Fazer meu check-in" onPress={onOpenCheckin} />
          </View>
        )}
      </Card>

      <Text style={[t.muted, { fontSize: 12, textAlign: "center", marginTop: 8 }]}>
        Em emergência, procure ajuda imediata ou ligue 188 (CVV, 24h).
      </Text>
    </ScrollView>
  );
}
