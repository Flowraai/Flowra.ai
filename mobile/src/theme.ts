import { StyleSheet } from "react-native";

export const colors = {
  bg: "#f4f6f5",
  surface: "#ffffff",
  ink: "#132a26",
  muted: "#6b7f79",
  line: "#e2e8e5",
  accent: "#178a6b",
  accentSoft: "#d9efe8",
  danger: "#c0392b",
  good: "#178a6b",
};

export const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 18 },
  h1: { fontSize: 26, fontWeight: "800", color: colors.ink },
  sub: { fontSize: 15, color: colors.muted, marginTop: 2 },
  card: {
    backgroundColor: colors.surface, borderRadius: 16, padding: 16, marginTop: 14,
    borderWidth: 1, borderColor: colors.line,
  },
  cardTitle: { fontSize: 16, fontWeight: "700", color: colors.ink, marginBottom: 6 },
  muted: { color: colors.muted, fontSize: 14 },
  input: {
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: colors.ink, marginTop: 10,
  },
  btn: {
    backgroundColor: colors.accent, borderRadius: 12, paddingVertical: 14, alignItems: "center",
    marginTop: 12,
  },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  btnGhost: {
    backgroundColor: "transparent", borderWidth: 1, borderColor: colors.line, borderRadius: 12,
    paddingVertical: 12, alignItems: "center", marginTop: 10,
  },
  btnGhostText: { color: colors.ink, fontSize: 15, fontWeight: "600" },
  link: { color: colors.accent, fontSize: 14, fontWeight: "600", marginTop: 14, textAlign: "center" },
  error: { color: colors.danger, fontSize: 14, marginTop: 10 },
  done: { color: colors.good, fontSize: 16, fontWeight: "700" },
  metricGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 6 },
  metric: {
    width: "47%", backgroundColor: colors.bg, borderRadius: 12, borderWidth: 1, borderColor: colors.line,
    paddingVertical: 12, alignItems: "center",
  },
  metricVal: { fontSize: 18, fontWeight: "800", color: colors.ink },
  metricLabel: { fontSize: 12, color: colors.muted, marginTop: 2 },
});
