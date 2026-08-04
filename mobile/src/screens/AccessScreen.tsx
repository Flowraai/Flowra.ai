import { useState } from "react";
import { KeyboardAvoidingView, Platform, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import { saveToken } from "../storage";
import { tokenFromInput } from "../linking";
import { Button, text } from "../components/ui";
import { useTheme } from "../theme";

export function AccessScreen({ onAuthed }: { onAuthed: () => void }) {
  const { theme } = useTheme();
  const t = text(theme);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    // Aceita o código puro ou o link colado (extrai o token deste).
    const value = tokenFromInput(token);
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      await patientApi.today(value); // valida o token
      await saveToken(value);
      onAuthed();
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 401
          ? "Código inválido. Confira o link enviado pelo seu médico."
          : "Não foi possível conectar. Tente novamente.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1, padding: 24, justifyContent: "center", gap: 16 }}
      >
        <View style={{ alignItems: "center", marginBottom: 8 }}>
          <View
            style={{
              width: 56,
              height: 56,
              borderRadius: 16,
              backgroundColor: theme.accent,
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 12,
            }}
          >
            <Text style={{ fontSize: 26 }}>🌿</Text>
          </View>
          <Text style={t.h1}>Flowra Care</Text>
          <Text style={[t.muted, { textAlign: "center", marginTop: 6 }]}>
            Seu acompanhamento diário. Cole o código de acesso que seu médico enviou.
          </Text>
        </View>

        <View style={{ gap: 8 }}>
          <Text style={t.label}>Código ou link de acesso</Text>
          <TextInput
            value={token}
            onChangeText={setToken}
            placeholder="cole o código ou o link do seu médico"
            placeholderTextColor={theme.muted}
            autoCapitalize="none"
            autoCorrect={false}
            style={{
              backgroundColor: theme.surface2,
              borderColor: theme.line,
              borderWidth: 1,
              borderRadius: 12,
              padding: 14,
              color: theme.ink,
              fontSize: 15,
            }}
          />
        </View>

        {error ? <Text style={{ color: theme.red, fontWeight: "600" }}>{error}</Text> : null}

        <Button label={busy ? "Conectando…" : "Entrar"} onPress={connect} disabled={busy || !token.trim()} />
        <Text style={[t.muted, { fontSize: 12, textAlign: "center" }]}>
          Seus dados são protegidos. Em emergência, procure ajuda imediata ou ligue 188 (CVV).
        </Text>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
