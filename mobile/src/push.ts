// Registro de push (Expo Notifications). Só roda em dispositivo físico.

import { Platform } from "react-native";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { patientApi } from "./api/endpoints";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/** Pede permissão, obtém o Expo push token e registra no backend. Best-effort. */
export async function registerForPush(): Promise<void> {
  if (!Device.isDevice) return; // push não funciona em emulador
  try {
    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== "granted") {
      status = (await Notifications.requestPermissionsAsync()).status;
    }
    if (status !== "granted") return;

    const projectId =
      Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    const tokenData = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    const platform = Platform.OS === "ios" ? "ios" : "android";
    await patientApi.registerDevice(tokenData.data, platform);
  } catch {
    /* push é best-effort; falha não bloqueia o app */
  }
}
