import { useEffect, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native";
import { patientApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import { tokenFromInput } from "../linking";
import { Button, text } from "../components/ui";
import { useTheme, type Theme } from "../theme";

type Mode = "login" | "activate" | "forgot" | "reset";

// Máscara leve de CPF (000.000.000-00) só para exibição; enviamos os dígitos.
function maskCpf(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 11);
  return d
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

function Field(props: {
  theme: Theme;
  value: string;
  onChangeText: (v: string) => void;
  placeholder: string;
  secure?: boolean;
  numeric?: boolean;
}) {
  const { theme } = props;
  return (
    <TextInput
      value={props.value}
      onChangeText={props.onChangeText}
      placeholder={props.placeholder}
      placeholderTextColor={theme.muted}
      secureTextEntry={props.secure}
      keyboardType={props.numeric ? "number-pad" : "default"}
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
  );
}

export function AccessScreen({
  inviteToken,
  onAuthed,
}: {
  // Token de convite vindo do deep link (primeira entrada). Se presente, abrimos
  // direto em "criar acesso".
  inviteToken?: string | null;
  onAuthed: (sessionToken: string) => void;
}) {
  const { theme } = useTheme();
  const t = text(theme);

  const [mode, setMode] = useState<Mode>(inviteToken ? "activate" : "login");
  const [invite, setInvite] = useState(inviteToken ?? "");
  const [cpf, setCpf] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [name, setName] = useState<string | null>(null);

  const cpfDigits = cpf.replace(/\D/g, "");

  useEffect(() => {
    if (inviteToken) {
      setInvite(inviteToken);
      setMode("activate");
    }
  }, [inviteToken]);

  // Ao ter um token de convite, busca o nome do paciente para uma saudação.
  useEffect(() => {
    const tok = tokenFromInput(invite);
    if (mode !== "activate" || !tok) return;
    let active = true;
    patientApi
      .account(tok)
      .then((a) => {
        if (!active) return;
        setName(a.name);
        if (a.activated) {
          // Já tem senha: melhor entrar por CPF.
          setInfo("Este acesso já foi criado. Entre com seu CPF e senha.");
          setMode("login");
        }
      })
      .catch(() => {
        /* token inválido/expirado — o próprio activate mostrará o erro */
      });
    return () => {
      active = false;
    };
  }, [invite, mode]);

  function fail(e: unknown, fallback: string) {
    setError(e instanceof ApiError ? e.message : fallback);
  }

  async function doActivate() {
    const tok = tokenFromInput(invite);
    if (!tok || cpfDigits.length !== 11 || password.length < 6) return;
    setBusy(true);
    setError(null);
    try {
      const s = await patientApi.activate(tok, cpfDigits, password);
      onAuthed(s.access_token);
    } catch (e) {
      fail(e, "Não foi possível criar o acesso.");
    } finally {
      setBusy(false);
    }
  }

  async function doLogin() {
    if (cpfDigits.length !== 11 || !password) return;
    setBusy(true);
    setError(null);
    try {
      const s = await patientApi.login(cpfDigits, password);
      onAuthed(s.access_token);
    } catch (e) {
      fail(e, "Não foi possível entrar.");
    } finally {
      setBusy(false);
    }
  }

  async function doForgot() {
    if (cpfDigits.length !== 11) return;
    setBusy(true);
    setError(null);
    try {
      const r = await patientApi.forgotPassword(cpfDigits);
      setInfo(r.message);
      setMode("reset");
    } catch (e) {
      fail(e, "Não foi possível enviar o código.");
    } finally {
      setBusy(false);
    }
  }

  async function doReset() {
    if (cpfDigits.length !== 11 || code.trim().length < 4 || newPassword.length < 6) return;
    setBusy(true);
    setError(null);
    try {
      const s = await patientApi.resetPassword(cpfDigits, code.trim(), newPassword);
      onAuthed(s.access_token);
    } catch (e) {
      fail(e, "Não foi possível redefinir a senha.");
    } finally {
      setBusy(false);
    }
  }

  function go(m: Mode) {
    setError(null);
    setInfo(null);
    setMode(m);
  }

  const titles: Record<Mode, { h1: string; sub: string }> = {
    login: { h1: "Entrar", sub: "Acesse com seu CPF e senha." },
    activate: {
      h1: "Criar seu acesso",
      sub: `${name ? `Olá, ${name.split(" ")[0]}! ` : ""}Defina seu CPF e uma senha para entrar sempre que quiser.`,
    },
    forgot: {
      h1: "Recuperar senha",
      sub: "Informe seu CPF. Enviaremos um código ao seu WhatsApp/e-mail cadastrado.",
    },
    reset: { h1: "Redefinir senha", sub: info ?? "Digite o código recebido e crie uma nova senha." },
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 24, justifyContent: "center", flexGrow: 1, gap: 16 }}>
          <View style={{ alignItems: "center", marginBottom: 4 }}>
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
            <Text style={t.h1}>{titles[mode].h1}</Text>
            <Text style={[t.muted, { textAlign: "center", marginTop: 6 }]}>{titles[mode].sub}</Text>
          </View>

          {mode === "activate" && !inviteToken ? (
            <View style={{ gap: 8 }}>
              <Text style={t.label}>Código ou link de convite</Text>
              <Field
                theme={theme}
                value={invite}
                onChangeText={setInvite}
                placeholder="cole o código ou o link do seu médico"
              />
            </View>
          ) : null}

          <Field theme={theme} value={maskCpf(cpf)} onChangeText={setCpf} placeholder="CPF" numeric />

          {mode === "login" ? (
            <Field theme={theme} value={password} onChangeText={setPassword} placeholder="Senha" secure />
          ) : null}

          {mode === "activate" ? (
            <Field
              theme={theme}
              value={password}
              onChangeText={setPassword}
              placeholder="Crie uma senha (mín. 6 caracteres)"
              secure
            />
          ) : null}

          {mode === "reset" ? (
            <>
              <Field theme={theme} value={code} onChangeText={setCode} placeholder="Código recebido" numeric />
              <Field
                theme={theme}
                value={newPassword}
                onChangeText={setNewPassword}
                placeholder="Nova senha (mín. 6 caracteres)"
                secure
              />
            </>
          ) : null}

          {error ? <Text style={{ color: theme.red, fontWeight: "600" }}>{error}</Text> : null}

          {mode === "login" ? (
            <Button label={busy ? "Entrando…" : "Entrar"} onPress={doLogin} disabled={busy || cpfDigits.length !== 11 || !password} />
          ) : mode === "activate" ? (
            <Button
              label={busy ? "Criando…" : "Criar acesso e entrar"}
              onPress={doActivate}
              disabled={busy || !tokenFromInput(invite) || cpfDigits.length !== 11 || password.length < 6}
            />
          ) : mode === "forgot" ? (
            <Button label={busy ? "Enviando…" : "Enviar código"} onPress={doForgot} disabled={busy || cpfDigits.length !== 11} />
          ) : (
            <Button
              label={busy ? "Salvando…" : "Redefinir e entrar"}
              onPress={doReset}
              disabled={busy || cpfDigits.length !== 11 || code.trim().length < 4 || newPassword.length < 6}
            />
          )}

          <View style={{ alignItems: "center", gap: 10, marginTop: 4 }}>
            {mode === "login" ? (
              <>
                <Link theme={theme} label="Esqueci minha senha" onPress={() => go("forgot")} />
                <Link theme={theme} label="Tenho um convite — criar acesso" onPress={() => go("activate")} />
              </>
            ) : null}
            {mode === "activate" ? <Link theme={theme} label="Já tenho acesso — entrar" onPress={() => go("login")} /> : null}
            {mode === "forgot" || mode === "reset" ? (
              <Link theme={theme} label="Voltar para entrar" onPress={() => go("login")} />
            ) : null}
          </View>

          <Text style={[t.muted, { fontSize: 12, textAlign: "center", marginTop: 8 }]}>
            Seus dados são protegidos. Em emergência, procure ajuda imediata ou ligue 188 (CVV).
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Link({ theme, label, onPress }: { theme: Theme; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={8}>
      <Text style={{ color: theme.accent, fontWeight: "700", fontSize: 14 }}>{label}</Text>
    </Pressable>
  );
}
