import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { getToken, patient, setToken, type PatientToday } from "./src/api";
import { Auth } from "./src/screens/Auth";
import { Today } from "./src/screens/Today";
import { colors } from "./src/theme";

type State = "loading" | "auth" | "app";

export default function App() {
  const [state, setState] = useState<State>("loading");
  const [today, setToday] = useState<PatientToday | null>(null);

  const boot = useCallback(async () => {
    const token = await getToken();
    if (!token) {
      setState("auth");
      return;
    }
    try {
      setToday(await patient.today());
      setState("app");
    } catch {
      await setToken(null);
      setState("auth");
    }
  }, []);

  useEffect(() => {
    boot();
  }, [boot]);

  async function logout() {
    await setToken(null);
    setToday(null);
    setState("auth");
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <StatusBar style="dark" />
      {state === "loading" ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : state === "auth" ? (
        <Auth onAuthed={boot} />
      ) : today ? (
        <Today today={today} onLogout={logout} />
      ) : null}
    </View>
  );
}
