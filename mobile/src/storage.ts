// Guarda o token de acesso do paciente com segurança (Keychain/Keystore).

import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "flowra_patient_token";

let cached: string | null = null;

export async function loadToken(): Promise<string | null> {
  if (cached !== null) return cached;
  try {
    cached = await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    cached = null;
  }
  return cached;
}

export async function saveToken(token: string): Promise<void> {
  cached = token;
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
}

export async function clearToken(): Promise<void> {
  cached = null;
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export function currentToken(): string | null {
  return cached;
}
