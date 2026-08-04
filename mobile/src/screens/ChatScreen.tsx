import { useEffect, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { ChatMessage } from "../api/types";
import { ErrorView, Loading } from "../components/ui";
import { useTheme } from "../theme";

export function ChatScreen() {
  const { theme } = useTheme();
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  function load() {
    setError(null);
    patientApi
      .messages()
      .then((m) => setMessages([...m].reverse())) // API devolve desc; exibimos asc
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a conversa."));
  }
  useEffect(load, []);

  async function send() {
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      const msg = await patientApi.sendMessage(body);
      setMessages((prev) => [...(prev ?? []), msg]);
      setDraft("");
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
    } catch {
      /* ignore */
    } finally {
      setSending(false);
    }
  }

  if (error) return <ErrorView message={error} onRetry={load} />;
  if (!messages) return <Loading label="Carregando…" />;

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={90}
    >
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: false })}
      >
        {messages.length === 0 ? (
          <Text style={{ color: theme.muted, textAlign: "center", marginTop: 40 }}>
            Converse com seu médico por aqui.
          </Text>
        ) : (
          messages.map((m) => {
            const mine = m.sender === "patient";
            return (
              <View
                key={m.id}
                style={{
                  alignSelf: mine ? "flex-end" : "flex-start",
                  backgroundColor: mine ? theme.accent : theme.surface,
                  borderColor: mine ? theme.accent : theme.line,
                  borderWidth: 1,
                  borderRadius: 14,
                  paddingVertical: 9,
                  paddingHorizontal: 12,
                  maxWidth: "82%",
                }}
              >
                <Text style={{ color: mine ? theme.onAccent : theme.ink, fontSize: 15 }}>{m.body}</Text>
              </View>
            );
          })
        )}
      </ScrollView>

      <View
        style={{
          flexDirection: "row",
          gap: 8,
          padding: 12,
          borderTopWidth: 1,
          borderTopColor: theme.line,
          backgroundColor: theme.surface,
        }}
      >
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder="Escreva uma mensagem…"
          placeholderTextColor={theme.muted}
          style={{
            flex: 1,
            backgroundColor: theme.surface2,
            borderColor: theme.line,
            borderWidth: 1,
            borderRadius: 999,
            paddingHorizontal: 16,
            paddingVertical: 10,
            color: theme.ink,
            fontSize: 15,
          }}
        />
        <Pressable
          onPress={send}
          disabled={sending || !draft.trim()}
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            backgroundColor: theme.accent,
            alignItems: "center",
            justifyContent: "center",
            opacity: sending || !draft.trim() ? 0.5 : 1,
          }}
        >
          <Text style={{ color: theme.onAccent, fontSize: 18 }}>➤</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
