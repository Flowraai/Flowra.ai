import { useColorScheme } from "react-native";

export interface Theme {
  bg: string;
  surface: string;
  surface2: string;
  ink: string;
  muted: string;
  line: string;
  accent: string;
  accentInk: string;
  accentSoft: string;
  onAccent: string;
  green: string;
  yellow: string;
  orange: string;
  red: string;
}

const light: Theme = {
  bg: "#f4f7f6",
  surface: "#ffffff",
  surface2: "#eef3f1",
  ink: "#14201d",
  muted: "#5c6c68",
  line: "#e2e9e6",
  accent: "#0e7c6e",
  accentInk: "#0a5a50",
  accentSoft: "#e2f1ed",
  onAccent: "#ffffff",
  green: "#2e9e6b",
  yellow: "#b9890a",
  orange: "#da7429",
  red: "#d3423a",
};

const dark: Theme = {
  bg: "#0d1413",
  surface: "#141d1b",
  surface2: "#1b2523",
  ink: "#e8eeeb",
  muted: "#94a39e",
  line: "#26312f",
  accent: "#34b3a2",
  accentInk: "#6fd4c6",
  accentSoft: "#17322d",
  onAccent: "#06211d",
  green: "#46ba80",
  yellow: "#dbb03c",
  orange: "#ef8e48",
  red: "#ec6a62",
};

export function useTheme(): { theme: Theme; scheme: "light" | "dark" } {
  const scheme = useColorScheme() === "dark" ? "dark" : "light";
  return { theme: scheme === "dark" ? dark : light, scheme };
}
