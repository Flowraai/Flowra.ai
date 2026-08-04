import { useState } from "react";
import { Image, Pressable, Text, View } from "react-native";
import { Audio } from "expo-av";
import { attachmentUrl, authHeader } from "../api/client";
import type { MessageAttachment } from "../api/types";
import { useTheme } from "../theme";

function kind(a: MessageAttachment): "image" | "audio" | "file" {
  const ct = a.content_type ?? a.type ?? "";
  if (ct.startsWith("image/")) return "image";
  if (ct.startsWith("audio/")) return "audio";
  return "file";
}

function href(a: MessageAttachment): string {
  return a.id ? attachmentUrl(a.id) : a.url;
}

export function AttachmentView({ attachment, mine }: { attachment: MessageAttachment; mine: boolean }) {
  const { theme } = useTheme();
  const k = kind(attachment);
  const uri = href(attachment);

  if (k === "image") {
    return (
      <Image
        source={{ uri, headers: authHeader() }}
        style={{ width: 180, height: 180, borderRadius: 10, marginTop: 6, backgroundColor: theme.surface2 }}
        resizeMode="cover"
      />
    );
  }
  if (k === "audio") {
    return <AudioBubble uri={uri} mine={mine} />;
  }
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 6 }}>
      <Text style={{ fontSize: 15 }}>📎</Text>
      <Text style={{ color: mine ? theme.onAccent : theme.ink, fontSize: 13.5, fontWeight: "600" }}>
        {attachment.filename ?? "arquivo"}
      </Text>
    </View>
  );
}

function AudioBubble({ uri, mine }: { uri: string; mine: boolean }) {
  const { theme } = useTheme();
  const [playing, setPlaying] = useState(false);
  const [sound, setSound] = useState<Audio.Sound | null>(null);

  async function toggle() {
    if (playing && sound) {
      await sound.pauseAsync();
      setPlaying(false);
      return;
    }
    if (sound) {
      await sound.playAsync();
      setPlaying(true);
      return;
    }
    const { sound: s } = await Audio.Sound.createAsync({ uri, headers: authHeader() }, { shouldPlay: true });
    s.setOnPlaybackStatusUpdate((st) => {
      if (st.isLoaded && st.didJustFinish) setPlaying(false);
    });
    setSound(s);
    setPlaying(true);
  }

  const color = mine ? theme.onAccent : theme.accentInk;
  return (
    <Pressable onPress={toggle} style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 6 }}>
      <Text style={{ fontSize: 18, color }}>{playing ? "⏸" : "▶"}</Text>
      <Text style={{ color, fontSize: 13.5, fontWeight: "600" }}>Áudio</Text>
    </Pressable>
  );
}
