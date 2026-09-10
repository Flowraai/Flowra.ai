import { useState } from "react";
import { Text, TextInput, TouchableOpacity, View, ScrollView } from "react-native";
import { auth, ApiError, setToken } from "../api";
import { s } from "../theme";

type Mode = "login" | "forgot" | "reset";

function maskCpf(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 11);
  return d
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

export function Auth({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [cpf, setCpf] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const digits = cpf.replace(/\D/g, "");

  function fail(e: unknown, fallback: string) {
    setError(e instanceof ApiError ? e.message : fallback);
  }

  async function login() {
    if (digits.length !== 11 || !password) return;
    setBusy(true); setError(null);
    try {
      const sess = await auth.login(digits, password);
      await setToken(sess.access_token);
      onAuthed();
    } catch (e) { fail(e, "Não foi possível entrar."); } finally { setBusy(false); }
  }

  async function forgot() {
    if (digits.length !== 11) return;
    setBusy(true); setError(null);
    try {
      const r = await auth.forgot(digits);
      setInfo(r.message);
      setMode("reset");
    } catch (e) { fail(e, "Não foi possível enviar o código."); } finally { setBusy(false); }
  }

  async function reset() {
    if (digits.length !== 11 || code.trim().length < 4 || newPassword.length < 6) return;
    setBusy(true); setError(null);
    try {
      const sess = await auth.reset(digits, code.trim(), newPassword);
      await setToken(sess.access_token);
      onAuthed();
    } catch (e) { fail(e, "Não foi possível redefinir."); } finally { setBusy(false); }
  }

  return (
    <ScrollView contentContainerStyle={[s.pad, { paddingTop: 60 }]}>
      <Text style={s.h1}>Flowra Care</Text>
      <Text style={s.sub}>Acompanhamento do paciente</Text>

      {mode === "login" ? (
        <View style={s.card}>
          <Text style={s.cardTitle}>Entrar</Text>
          <TextInput style={s.input} placeholder="CPF" keyboardType="number-pad"
            value={maskCpf(cpf)} onChangeText={setCpf} />
          <TextInput style={s.input} placeholder="Senha" secureTextEntry
            value={password} onChangeText={setPassword} />
          {error ? <Text style={s.error}>{error}</Text> : null}
          <TouchableOpacity style={s.btn} onPress={login} disabled={busy}>
            <Text style={s.btnText}>{busy ? "Entrando…" : "Entrar"}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => { setError(null); setInfo(null); setMode("forgot"); }}>
            <Text style={s.link}>Esqueci minha senha</Text>
          </TouchableOpacity>
        </View>
      ) : mode === "forgot" ? (
        <View style={s.card}>
          <Text style={s.cardTitle}>Recuperar senha</Text>
          <Text style={s.muted}>Informe seu CPF. Enviaremos um código ao seu WhatsApp/e-mail.</Text>
          <TextInput style={s.input} placeholder="CPF" keyboardType="number-pad"
            value={maskCpf(cpf)} onChangeText={setCpf} />
          {error ? <Text style={s.error}>{error}</Text> : null}
          <TouchableOpacity style={s.btn} onPress={forgot} disabled={busy}>
            <Text style={s.btnText}>{busy ? "Enviando…" : "Enviar código"}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => { setError(null); setMode("login"); }}>
            <Text style={s.link}>Voltar</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={s.card}>
          <Text style={s.cardTitle}>Redefinir senha</Text>
          {info ? <Text style={s.muted}>{info}</Text> : null}
          <TextInput style={s.input} placeholder="CPF" keyboardType="number-pad"
            value={maskCpf(cpf)} onChangeText={setCpf} />
          <TextInput style={s.input} placeholder="Código recebido" keyboardType="number-pad"
            value={code} onChangeText={setCode} />
          <TextInput style={s.input} placeholder="Nova senha (mín. 6)" secureTextEntry
            value={newPassword} onChangeText={setNewPassword} />
          {error ? <Text style={s.error}>{error}</Text> : null}
          <TouchableOpacity style={s.btn} onPress={reset} disabled={busy}>
            <Text style={s.btnText}>{busy ? "Salvando…" : "Redefinir e entrar"}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => { setError(null); setMode("login"); }}>
            <Text style={s.link}>Voltar</Text>
          </TouchableOpacity>
        </View>
      )}

      <Text style={[s.muted, { marginTop: 20, textAlign: "center" }]}>
        Primeiro acesso? Abra o link de convite que seu médico enviou para criar sua senha.
      </Text>
    </ScrollView>
  );
}
