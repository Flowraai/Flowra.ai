import { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, SafeAreaView, StatusBar, Text, View } from "react-native";
import * as Linking from "expo-linking";
import { loadToken, saveToken, clearToken } from "./src/storage";
import { registerForPush } from "./src/push";
import { tokenFromUrl } from "./src/linking";
import { patientApi } from "./src/api/endpoints";
import { useTheme } from "./src/theme";
import { Loading } from "./src/components/ui";
import { AccessScreen } from "./src/screens/AccessScreen";
import { TodayScreen } from "./src/screens/TodayScreen";
import { CheckinScreen } from "./src/screens/CheckinScreen";
import { MedicationScreen } from "./src/screens/MedicationScreen";
import { ChatScreen } from "./src/screens/ChatScreen";
import { AiChatScreen } from "./src/screens/AiChatScreen";
import { AgendaScreen } from "./src/screens/AgendaScreen";

type Tab = "hoje" | "medicacao" | "agenda" | "chat" | "apoio";
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "hoje", label: "Hoje", icon: "🏠" },
  { key: "medicacao", label: "Remédios", icon: "💊" },
  { key: "agenda", label: "Agenda", icon: "📅" },
  { key: "chat", label: "Médico", icon: "💬" },
  { key: "apoio", label: "Apoio", icon: "✨" },
];

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [connecting, setConnecting] = useState(false);

  const connectWithToken = useCallback(async (token: string): Promise<boolean> => {
    setConnecting(true);
    try {
      await patientApi.today(token); // valida o código do link
      await saveToken(token);
      setAuthed(true);
      registerForPush();
      return true;
    } catch {
      return false;
    } finally {
      setConnecting(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      const tok = await loadToken();
      if (tok) {
        if (active) setAuthed(true);
        registerForPush();
        return;
      }
      // Sem sessão salva: tenta o código de um deep link de abertura.
      const initialUrl = await Linking.getInitialURL();
      const linked = tokenFromUrl(initialUrl);
      if (linked && (await connectWithToken(linked))) return;
      if (active) setAuthed(false);
    }
    bootstrap();

    // Deep link com o app já aberto.
    const sub = Linking.addEventListener("url", ({ url }) => {
      const t = tokenFromUrl(url);
      if (t) connectWithToken(t);
    });
    return () => {
      active = false;
      sub.remove();
    };
  }, [connectWithToken]);

  if (authed === null || connecting) {
    return <Splash />;
  }
  if (!authed) {
    return (
      <AccessScreen
        onAuthed={() => {
          setAuthed(true);
          registerForPush();
        }}
      />
    );
  }
  return <Main onLogout={() => clearToken().then(() => setAuthed(false))} />;
}

function Splash() {
  const { theme, scheme } = useTheme();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }}>
      <StatusBar barStyle={scheme === "dark" ? "light-content" : "dark-content"} />
      <Loading />
    </SafeAreaView>
  );
}

function Main({ onLogout }: { onLogout: () => void }) {
  const { theme, scheme } = useTheme();
  const [tab, setTab] = useState<Tab>("hoje");
  const [showCheckin, setShowCheckin] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }}>
      <StatusBar barStyle={scheme === "dark" ? "light-content" : "dark-content"} />

      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          paddingHorizontal: 20,
          paddingVertical: 12,
          borderBottomWidth: 1,
          borderBottomColor: theme.line,
        }}
      >
        <Text style={{ color: theme.ink, fontWeight: "800", fontSize: 16, flex: 1 }}>Flowra Care</Text>
        <Pressable onPress={onLogout} hitSlop={10}>
          <Text style={{ color: theme.muted, fontWeight: "600" }}>Sair</Text>
        </Pressable>
      </View>

      <View style={{ flex: 1 }}>
        {tab === "hoje" ? (
          <TodayScreen onOpenCheckin={() => setShowCheckin(true)} nonce={nonce} />
        ) : tab === "medicacao" ? (
          <MedicationScreen />
        ) : tab === "agenda" ? (
          <AgendaScreen />
        ) : tab === "chat" ? (
          <ChatScreen />
        ) : (
          <AiChatScreen />
        )}
      </View>

      {toast ? (
        <View
          style={{
            position: "absolute",
            bottom: 92,
            left: 20,
            right: 20,
            backgroundColor: theme.accent,
            borderRadius: 12,
            padding: 14,
          }}
        >
          <Text style={{ color: theme.onAccent, fontWeight: "600", textAlign: "center" }}>{toast}</Text>
        </View>
      ) : null}

      <View
        style={{
          flexDirection: "row",
          borderTopWidth: 1,
          borderTopColor: theme.line,
          backgroundColor: theme.surface,
          paddingBottom: 6,
        }}
      >
        {TABS.map((tb) => {
          const on = tab === tb.key;
          return (
            <Pressable
              key={tb.key}
              onPress={() => setTab(tb.key)}
              style={{ flex: 1, alignItems: "center", paddingVertical: 10, gap: 2 }}
            >
              <Text style={{ fontSize: 20, opacity: on ? 1 : 0.55 }}>{tb.icon}</Text>
              <Text style={{ fontSize: 11.5, fontWeight: "600", color: on ? theme.accent : theme.muted }}>
                {tb.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Modal visible={showCheckin} animationType="slide" presentationStyle="pageSheet">
        <CheckinScreen
          onClose={() => setShowCheckin(false)}
          onDone={(msg) => {
            setShowCheckin(false);
            setNonce((n) => n + 1);
            setToast(msg);
          }}
        />
      </Modal>
    </SafeAreaView>
  );
}
