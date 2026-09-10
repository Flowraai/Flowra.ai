import { useCallback, useEffect, useState } from "react";
import { Alert, RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { patient, ApiError, type PatientToday, type WearableSummary } from "../api";
import { checkAvailability, connectHealth, readDailyHealth } from "../health";
import { s, colors } from "../theme";

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name;
}
function sleepLabel(min: number | null | undefined): string {
  if (min == null) return "—";
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, "0")}`;
}
function num(v: number | null | undefined): string {
  return v == null ? "—" : v.toLocaleString("pt-BR");
}

export function Today({ today, onLogout }: { today: PatientToday; onLogout: () => void }) {
  const [wear, setWear] = useState<WearableSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setWear(await patient.wearable());
    } catch {
      /* mantém */
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function syncHealth() {
    setBusy(true);
    setMsg(null);
    try {
      const avail = await checkAvailability();
      if (avail !== "ok") {
        Alert.alert(
          "Health Connect",
          avail === "update_required"
            ? "Atualize o app Health Connect na Play Store para continuar."
            : "Instale o app Health Connect (Play Store) e conecte sua pulseira/relógio a ele.",
        );
        return;
      }
      const granted = await connectHealth();
      if (!granted) {
        setMsg("Precisamos da sua permissão no Health Connect para ler os dados.");
        return;
      }
      const days = await readDailyHealth(14);
      if (days.length === 0) {
        setMsg("Nenhum dado encontrado ainda. Sincronize sua pulseira com o Health Connect e tente de novo.");
        return;
      }
      setWear(await patient.pushHealth("health_connect", days));
      setMsg("Dados atualizados ✓");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Não foi possível sincronizar agora.");
    } finally {
      setBusy(false);
    }
  }

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const latest = wear?.latest;

  return (
    <ScrollView
      style={s.screen}
      contentContainerStyle={[s.pad, { paddingTop: 56 }]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text style={s.h1}>Olá, {firstName(today.patient_name)} 👋</Text>
        <TouchableOpacity onPress={onLogout}>
          <Text style={{ color: colors.muted, fontWeight: "600" }}>Sair</Text>
        </TouchableOpacity>
      </View>
      <Text style={s.sub}>Como você está hoje?</Text>

      <View style={s.card}>
        {today.checked_in_today ? (
          <Text style={s.done}>✓ Check-in de hoje concluído</Text>
        ) : (
          <>
            <Text style={s.cardTitle}>Check-in de hoje</Text>
            <Text style={s.muted}>
              O check-in diário estará disponível no app em breve. Por enquanto, use o link do seu
              médico no navegador.
            </Text>
          </>
        )}
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>⌚ Meu dispositivo</Text>
        {latest ? (
          <>
            <View style={s.metricGrid}>
              <View style={s.metric}>
                <Text style={s.metricVal}>{sleepLabel(latest.sleep_minutes)}</Text>
                <Text style={s.metricLabel}>😴 sono</Text>
              </View>
              <View style={s.metric}>
                <Text style={s.metricVal}>{num(latest.resting_hr)}</Text>
                <Text style={s.metricLabel}>❤️ bpm repouso</Text>
              </View>
              <View style={s.metric}>
                <Text style={s.metricVal}>{num(latest.hrv_ms)}</Text>
                <Text style={s.metricLabel}>📈 HRV (ms)</Text>
              </View>
              <View style={s.metric}>
                <Text style={s.metricVal}>{num(latest.steps)}</Text>
                <Text style={s.metricLabel}>👟 passos</Text>
              </View>
            </View>
            <TouchableOpacity style={s.btnGhost} onPress={syncHealth} disabled={busy}>
              <Text style={s.btnGhostText}>{busy ? "Sincronizando…" : "Atualizar agora"}</Text>
            </TouchableOpacity>
          </>
        ) : (
          <>
            <Text style={s.muted}>
              Conecte seu relógio ou pulseira (Mi Band, Samsung, Google Fit…) pelo Health Connect
              para acompanhar sono, batimentos e atividade junto do seu médico.
            </Text>
            <TouchableOpacity style={s.btn} onPress={syncHealth} disabled={busy}>
              <Text style={s.btnText}>{busy ? "Conectando…" : "Conectar dispositivo"}</Text>
            </TouchableOpacity>
          </>
        )}
        {msg ? <Text style={[s.muted, { marginTop: 10 }]}>{msg}</Text> : null}
      </View>
    </ScrollView>
  );
}
