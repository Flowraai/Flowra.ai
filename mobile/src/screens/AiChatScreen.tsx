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

function localMsg(sender: "patient", body: string): ChatMessage {
  return {
    id: `local-${Date.now()}`,
    sender,
    body,
    attachments: [],
    read_at: null,
    created_at: new Date().toISOString(),
  };
}

export function AiChatScreen() {
  const { theme } = useTheme();
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  function load() {
    setError(null);
    patientApi
      .aiHistory()
      .then((m) => setMessages([...m].reverse()))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a conversa."));
  }
  useEffect(load, []);

  async function send() {
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    setDraft("");
    setMessages((prev) => [...(prev ?? []), localMsg("patient", body)]);
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 40);
    try {
      const reply = await patientApi.aiSend(body);
      setMessages((prev) => [...(prev ?? []), reply]);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 40);
    } catch {
      setMessages((prev) => [
        ...(prev ?? []),
        {
          id: `err-${Date.now()}`,
          sender: "ai",
          body: "Não consegui responder agora. Se for urgente, fale com seu médico ou ligue 188 (CVV).",
          attachments: [],
          read_at: null,
          created_at: new Date().toISOString(),
        },
      ]);
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
      <View style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4 }}>
        <Text style={{ color: theme.muted, fontSize: 12.5, textAlign: "center" }}>
          Apoio da Flowra · assistente de conversa. Não substitui seu médico. Em emergência, ligue 188 (CVV).
        </Text>
      </View>

      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: false })}
      >
        {messages.length === 0 ? (
          <View style={{ alignItems: "center", marginTop: 32, gap: 8, paddingHorizontal: 16 }}>
            <Text style={{ fontSize: 34 }}>💬</Text>
            <Text style={{ color: theme.ink, fontSize: 16, fontWeight: "700" }}>Como você está agora?</Text>
            <Text style={{ color: theme.muted, textAlign: "center", fontSize: 14 }}>
              Fale o que estiver sentindo. Estou aqui para te ouvir e apoiar entre as consultas.
            </Text>
          </View>
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
                  borderRadius: 16,
                  borderBottomRightRadius: mine ? 5 : 16,
                  borderBottomLeftRadius: mine ? 16 : 5,
                  paddingVertical: 10,
                  paddingHorizontal: 13,
                  maxWidth: "85%",
                }}
              >
                {!mine ? (
                  <Text style={{ color: theme.accentInk, fontSize: 10.5, fontWeight: "800", marginBottom: 3, letterSpacing: 0.4 }}>
                    APOIO FLOWRA
                  </Text>
                ) : null}
                <Text style={{ color: mine ? theme.onAccent : theme.ink, fontSize: 15, lineHeight: 21 }}>{m.body}</Text>
              </View>
            );
          })
        )}
        {sending ? (
          <View style={{ alignSelf: "flex-start", paddingHorizontal: 6 }}>
            <Text style={{ color: theme.muted, fontSize: 13 }}>escrevendo…</Text>
          </View>
        ) : null}
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
          placeholder="Escreva como está se sentindo…"
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
