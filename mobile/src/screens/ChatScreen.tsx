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
import type { AttachmentRef, ChatMessage, MessageAttachment } from "../api/types";
import { AttachmentView } from "../components/AttachmentView";
import { ErrorView, Loading } from "../components/ui";
import { AudioRecorder, pickAndUploadFile, pickAndUploadPhoto } from "../media";
import { useTheme } from "../theme";

function toPayload(refs: AttachmentRef[]): MessageAttachment[] {
  return refs.map((r) => ({ id: r.id, url: r.url, content_type: r.content_type, filename: r.filename }));
}

export function ChatScreen() {
  const { theme } = useTheme();
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<AttachmentRef[]>([]);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const recorder = useRef(new AudioRecorder());

  function load() {
    setError(null);
    patientApi
      .messages()
      .then((m) => setMessages([...m].reverse()))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a conversa."));
  }
  useEffect(load, []);

  async function attach(fn: () => Promise<AttachmentRef | null>) {
    setNote(null);
    setUploading(true);
    try {
      const ref = await fn();
      if (ref) setPending((p) => [...p, ref]);
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Não foi possível anexar.");
    } finally {
      setUploading(false);
    }
  }

  async function toggleRecord() {
    setNote(null);
    if (recording) {
      setRecording(false);
      setUploading(true);
      try {
        const ref = await recorder.current.stopAndUpload();
        if (ref) setPending((p) => [...p, ref]);
      } catch (e) {
        setNote(e instanceof ApiError ? e.message : "Falha ao enviar o áudio.");
      } finally {
        setUploading(false);
      }
    } else {
      const ok = await recorder.current.start();
      if (ok) setRecording(true);
      else setNote("Permissão de microfone negada.");
    }
  }

  async function send() {
    const body = draft.trim();
    if ((!body && pending.length === 0) || sending) return;
    setSending(true);
    try {
      const msg = await patientApi.sendMessage(body || "(anexo)", toPayload(pending));
      setMessages((prev) => [...(prev ?? []), msg]);
      setDraft("");
      setPending([]);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Não foi possível enviar.");
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
                {m.body && m.body !== "(anexo)" ? (
                  <Text style={{ color: mine ? theme.onAccent : theme.ink, fontSize: 15 }}>{m.body}</Text>
                ) : null}
                {(m.attachments ?? []).map((a, i) => (
                  <AttachmentView key={i} attachment={a} mine={mine} />
                ))}
              </View>
            );
          })
        )}
      </ScrollView>

      {pending.length > 0 || note ? (
        <View style={{ paddingHorizontal: 14, paddingBottom: 4, gap: 6 }}>
          {note ? <Text style={{ color: theme.red, fontSize: 12.5 }}>{note}</Text> : null}
          {pending.length > 0 ? (
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
              {pending.map((p, i) => (
                <Pressable
                  key={i}
                  onPress={() => setPending((prev) => prev.filter((_, idx) => idx !== i))}
                  style={{ backgroundColor: theme.surface2, borderRadius: 999, paddingVertical: 5, paddingHorizontal: 10 }}
                >
                  <Text style={{ color: theme.ink, fontSize: 12.5 }}>
                    {p.content_type.startsWith("image/") ? "🖼" : p.content_type.startsWith("audio/") ? "🎤" : "📎"}{" "}
                    {p.filename ?? "anexo"} ✕
                  </Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}

      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 6,
          padding: 10,
          borderTopWidth: 1,
          borderTopColor: theme.line,
          backgroundColor: theme.surface,
        }}
      >
        <IconBtn label="🖼" disabled={uploading || sending} onPress={() => attach(pickAndUploadPhoto)} />
        <IconBtn label="📎" disabled={uploading || sending} onPress={() => attach(pickAndUploadFile)} />
        <IconBtn label={recording ? "⏹" : "🎤"} active={recording} disabled={uploading || sending} onPress={toggleRecord} />
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder={uploading ? "Enviando anexo…" : "Mensagem…"}
          placeholderTextColor={theme.muted}
          style={{
            flex: 1,
            backgroundColor: theme.surface2,
            borderColor: theme.line,
            borderWidth: 1,
            borderRadius: 999,
            paddingHorizontal: 14,
            paddingVertical: 9,
            color: theme.ink,
            fontSize: 15,
          }}
        />
        <Pressable
          onPress={send}
          disabled={sending || uploading || (!draft.trim() && pending.length === 0)}
          style={{
            width: 42,
            height: 42,
            borderRadius: 21,
            backgroundColor: theme.accent,
            alignItems: "center",
            justifyContent: "center",
            opacity: sending || uploading || (!draft.trim() && pending.length === 0) ? 0.5 : 1,
          }}
        >
          <Text style={{ color: theme.onAccent, fontSize: 18 }}>➤</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function IconBtn({
  label,
  onPress,
  disabled,
  active,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  active?: boolean;
}) {
  const { theme } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={{
        width: 38,
        height: 38,
        borderRadius: 19,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: active ? theme.red : theme.surface2,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <Text style={{ fontSize: 17 }}>{label}</Text>
    </Pressable>
  );
}
