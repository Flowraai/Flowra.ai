import { useEffect, useState } from "react";
import { ScrollView, Text, TextInput, Pressable, View } from "react-native";
import { SafeAreaView } from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Question } from "../api/types";
import { Button, ErrorView, Loading, text } from "../components/ui";
import { useTheme, type Theme } from "../theme";

type Answers = Record<string, string | number>;

export function CheckinScreen({ onClose, onDone }: { onClose: () => void; onDone: (msg: string) => void }) {
  const { theme } = useTheme();
  const t = text(theme);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [freeText, setFreeText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    patientApi
      .protocol()
      .then((p) => active && setQuestions([...p.questions].sort((a, b) => a.position - b.position)))
      .catch((e) => active && setError(e instanceof ApiError ? e.message : "Falha ao carregar o check-in."));
    return () => {
      active = false;
    };
  }, []);

  const structured = (questions ?? []).filter((q) => q.type !== "free_text");
  const freeTextQ = (questions ?? []).find((q) => q.type === "free_text");
  const missing = structured.filter((q) => q.required && answers[q.code] === undefined);
  const canSubmit = missing.length === 0 && !submitting;

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await patientApi.submitCheckin(answers, freeText.trim() || null);
      onDone(res.message);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setSubmitError("Você já registrou seu check-in hoje.");
      else setSubmitError(e instanceof ApiError ? e.message : "Não foi possível enviar. Tente de novo.");
      setSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }}>
      <View style={{ flexDirection: "row", alignItems: "center", padding: 16, gap: 12 }}>
        <Pressable onPress={onClose} hitSlop={10}>
          <Text style={{ color: theme.accent, fontSize: 16, fontWeight: "600" }}>Fechar</Text>
        </Pressable>
        <Text style={[t.h2, { flex: 1 }]}>Check-in de hoje</Text>
      </View>

      {error ? (
        <ErrorView message={error} />
      ) : !questions ? (
        <Loading label="Carregando…" />
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, gap: 18, paddingBottom: 40 }}>
          {structured.map((q) => (
            <QuestionField
              key={q.code}
              q={q}
              theme={theme}
              value={answers[q.code]}
              onChange={(v) => setAnswers((prev) => ({ ...prev, [q.code]: v }))}
            />
          ))}

          {freeTextQ ? (
            <View style={{ gap: 8 }}>
              <Text style={{ color: theme.ink, fontSize: 15, fontWeight: "600" }}>{freeTextQ.text}</Text>
              <TextInput
                value={freeText}
                onChangeText={setFreeText}
                placeholder="Opcional…"
                placeholderTextColor={theme.muted}
                multiline
                style={{
                  backgroundColor: theme.surface,
                  borderColor: theme.line,
                  borderWidth: 1,
                  borderRadius: 12,
                  padding: 14,
                  minHeight: 90,
                  color: theme.ink,
                  fontSize: 15,
                  textAlignVertical: "top",
                }}
              />
            </View>
          ) : null}

          {submitError ? <Text style={{ color: theme.red, fontWeight: "600" }}>{submitError}</Text> : null}
          <Button
            label={submitting ? "Enviando…" : canSubmit ? "Enviar check-in" : `Responda ${missing.length} pergunta(s)`}
            onPress={submit}
            disabled={!canSubmit}
          />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function QuestionField({
  q,
  theme,
  value,
  onChange,
}: {
  q: Question;
  theme: Theme;
  value: string | number | undefined;
  onChange: (v: string | number) => void;
}) {
  return (
    <View style={{ gap: 10 }}>
      <Text style={{ color: theme.ink, fontSize: 15, fontWeight: "600" }}>{q.text}</Text>
      {q.type === "scale" ? (
        <Chips
          theme={theme}
          options={range(q.options?.min ?? 0, q.options?.max ?? 10).map((n) => ({ label: String(n), value: n }))}
          selected={value}
          onSelect={onChange}
        />
      ) : q.type === "choice" || q.type === "boolean" ? (
        <Chips
          theme={theme}
          options={(q.options?.choices ?? ["sim", "nao"]).map((c) => ({ label: prettyChoice(c), value: c }))}
          selected={value}
          onSelect={onChange}
        />
      ) : (
        <NumberInput theme={theme} unit={q.options?.unit} value={value} onChange={onChange} />
      )}
    </View>
  );
}

function Chips({
  theme,
  options,
  selected,
  onSelect,
}: {
  theme: Theme;
  options: { label: string; value: string | number }[];
  selected: string | number | undefined;
  onSelect: (v: string | number) => void;
}) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {options.map((o) => {
        const on = selected === o.value;
        return (
          <Pressable
            key={String(o.value)}
            onPress={() => onSelect(o.value)}
            style={{
              backgroundColor: on ? theme.accent : theme.surface,
              borderColor: on ? theme.accent : theme.line,
              borderWidth: 1,
              borderRadius: 999,
              paddingVertical: 9,
              paddingHorizontal: 15,
              minWidth: 44,
              alignItems: "center",
            }}
          >
            <Text style={{ color: on ? theme.onAccent : theme.ink, fontWeight: "600" }}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function NumberInput({
  theme,
  unit,
  value,
  onChange,
}: {
  theme: Theme;
  unit?: string;
  value: string | number | undefined;
  onChange: (v: number) => void;
}) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
      <TextInput
        keyboardType="number-pad"
        value={value === undefined ? "" : String(value)}
        onChangeText={(txt) => {
          const n = parseInt(txt.replace(/[^0-9]/g, ""), 10);
          if (!Number.isNaN(n)) onChange(n);
        }}
        placeholder="0"
        placeholderTextColor={theme.muted}
        style={{
          backgroundColor: theme.surface,
          borderColor: theme.line,
          borderWidth: 1,
          borderRadius: 12,
          padding: 12,
          minWidth: 90,
          color: theme.ink,
          fontSize: 16,
          textAlign: "center",
        }}
      />
      {unit ? <Text style={{ color: theme.muted }}>{unit}</Text> : null}
    </View>
  );
}

function range(min: number, max: number): number[] {
  const out: number[] = [];
  for (let i = min; i <= max; i++) out.push(i);
  return out;
}

function prettyChoice(c: string): string {
  const map: Record<string, string> = {
    sim: "Sim",
    nao: "Não",
    "não": "Não",
    mais_ou_menos: "Mais ou menos",
    parcialmente: "Parcialmente",
  };
  return map[c] ?? c;
}
