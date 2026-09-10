import { useEffect, useState } from "react";
import { Alert, Text, View } from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { WearableSummary } from "../api/types";
import { checkAvailability, readDailyHealth, requestHealthPermissions } from "../health";
import { Button, Card, text } from "./ui";
import { useTheme } from "../theme";

function sleepLabel(min: number | null | undefined): string {
  if (min == null) return "—";
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, "0")}`;
}
function num(v: number | null | undefined): string {
  return v == null ? "—" : v.toLocaleString("pt-BR");
}

export function DeviceCard() {
  const { theme } = useTheme();
  const t = text(theme);
  const [data, setData] = useState<WearableSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    try {
      setData(await patientApi.wearable());
    } catch {
      /* silencioso */
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function sync() {
    setBusy(true);
    setMsg(null);
    try {
      const avail = await checkAvailability();
      if (avail !== "ok") {
        Alert.alert(
          "Health Connect",
          avail === "update_required"
            ? "Atualize o app Health Connect na Play Store para continuar."
            : "Instale o app Health Connect (Play Store) e conecte sua pulseira/relógio a ele (Mi Fitness/Zepp, Samsung Health ou Google Fit).",
        );
        return;
      }
      const granted = await requestHealthPermissions();
      if (!granted) {
        setMsg("Precisamos da sua permissão no Health Connect para ler os dados.");
        return;
      }
      const days = await readDailyHealth(14);
      if (days.length === 0) {
        setMsg("Nenhum dado ainda. Sincronize sua pulseira com o Health Connect e tente de novo.");
        return;
      }
      setData(await patientApi.pushHealth("health_connect", days));
      setMsg("Dados atualizados ✓");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Não foi possível sincronizar agora.");
    } finally {
      setBusy(false);
    }
  }

  const latest = data?.latest;
  const metrics: { val: string; label: string }[] = [
    { val: sleepLabel(latest?.sleep_minutes), label: "😴 sono" },
    { val: num(latest?.resting_hr), label: "❤️ bpm repouso" },
    { val: num(latest?.hrv_ms), label: "📈 HRV (ms)" },
    { val: num(latest?.steps), label: "👟 passos" },
  ];

  return (
    <Card>
      <View style={{ gap: 10 }}>
        <Text style={t.h2}>⌚ Meu dispositivo</Text>
        {latest ? (
          <>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              {metrics.map((m) => (
                <View
                  key={m.label}
                  style={{
                    width: "47%",
                    backgroundColor: theme.surface2,
                    borderRadius: 12,
                    borderWidth: 1,
                    borderColor: theme.line,
                    paddingVertical: 12,
                    alignItems: "center",
                  }}
                >
                  <Text style={{ color: theme.ink, fontSize: 18, fontWeight: "800" }}>{m.val}</Text>
                  <Text style={{ color: theme.muted, fontSize: 12, marginTop: 2 }}>{m.label}</Text>
                </View>
              ))}
            </View>
            <Button label={busy ? "Sincronizando…" : "Atualizar agora"} variant="ghost" onPress={sync} disabled={busy} />
          </>
        ) : (
          <>
            <Text style={t.muted}>
              Conecte seu relógio ou pulseira (Mi Band, Samsung, Google Fit…) para acompanhar sono,
              batimentos e atividade junto do seu médico.
            </Text>
            <Button label={busy ? "Conectando…" : "Conectar dispositivo"} onPress={sync} disabled={busy} />
          </>
        )}
        {msg ? <Text style={[t.muted, { fontSize: 13 }]}>{msg}</Text> : null}
      </View>
    </Card>
  );
}
