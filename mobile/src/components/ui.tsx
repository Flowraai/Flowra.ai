import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";
import { useTheme, type Theme } from "../theme";

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  const { theme } = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: theme.surface,
          borderColor: theme.line,
          borderWidth: 1,
          borderRadius: 14,
          padding: 16,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function Button({
  label,
  onPress,
  variant = "primary",
  disabled,
}: {
  label: string;
  onPress: () => void;
  variant?: "primary" | "ghost";
  disabled?: boolean;
}) {
  const { theme } = useTheme();
  const primary = variant === "primary";
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => ({
        backgroundColor: primary ? theme.accent : "transparent",
        borderColor: primary ? "transparent" : theme.line,
        borderWidth: primary ? 0 : 1,
        borderRadius: 12,
        paddingVertical: 14,
        paddingHorizontal: 18,
        alignItems: "center",
        opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
      })}
    >
      <Text style={{ color: primary ? theme.onAccent : theme.ink, fontWeight: "700", fontSize: 15.5 }}>
        {label}
      </Text>
    </Pressable>
  );
}

export function Loading({ label }: { label?: string }) {
  const { theme } = useTheme();
  return (
    <View style={styles.center}>
      <ActivityIndicator color={theme.accent} />
      {label ? <Text style={{ color: theme.muted, marginTop: 10 }}>{label}</Text> : null}
    </View>
  );
}

export function ErrorView({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { theme } = useTheme();
  return (
    <View style={styles.center}>
      <Text style={{ color: theme.red, fontWeight: "600", textAlign: "center", marginBottom: 12 }}>
        {message}
      </Text>
      {onRetry ? <Button label="Tentar de novo" variant="ghost" onPress={onRetry} /> : null}
    </View>
  );
}

export const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32, gap: 4 },
});

export function text(theme: Theme) {
  return StyleSheet.create({
    h1: { color: theme.ink, fontSize: 26, fontWeight: "800", letterSpacing: -0.5 },
    h2: { color: theme.ink, fontSize: 19, fontWeight: "700" },
    muted: { color: theme.muted, fontSize: 14 },
    label: { color: theme.muted, fontSize: 13, fontWeight: "600" },
  });
}
