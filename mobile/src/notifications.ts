import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import type { AuthenticatedApi } from "./api";

const INSTALLATION_KEY = "sibling-rewards-installation-id";
let notificationsPromise: Promise<typeof import("expo-notifications")> | null = null;
let handlerConfigured = false;

export function pushNotificationsSupported(): boolean {
  return (
    Platform.OS !== "web" &&
    Constants.executionEnvironment !== "storeClient" &&
    Constants.appOwnership !== "expo"
  );
}

async function loadNotifications(): Promise<typeof import("expo-notifications")> {
  if (!pushNotificationsSupported()) {
    throw new Error(
      Platform.OS === "web"
        ? "Push notifications require the mobile app."
        : "Push notifications require a development build and are unavailable in Expo Go.",
    );
  }
  notificationsPromise ??= import("expo-notifications");
  const notifications = await notificationsPromise;
  if (!handlerConfigured) {
    notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldPlaySound: true,
        shouldSetBadge: false,
        shouldShowBanner: true,
        shouldShowList: true,
      }),
    });
    handlerConfigured = true;
  }
  return notifications;
}

export function addNotificationResponseListener(onRoute: (route: string) => void): () => void {
  if (!pushNotificationsSupported()) return () => undefined;

  let active = true;
  let remove: () => void = () => undefined;
  void loadNotifications()
    .then((notifications) => {
      const subscription = notifications.addNotificationResponseReceivedListener((response) => {
        const route = response.notification.request.content.data?.route;
        if (typeof route === "string" && route.startsWith("/")) onRoute(route);
      });
      if (active) remove = () => subscription.remove();
      else subscription.remove();
    })
    .catch(() => undefined);

  return () => {
    active = false;
    remove();
  };
}

export async function installationId(): Promise<string> {
  const existing = await SecureStore.getItemAsync(INSTALLATION_KEY);
  if (existing) return existing;
  const created = `install-${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random()
    .toString(36)
    .slice(2)}`;
  await SecureStore.setItemAsync(INSTALLATION_KEY, created);
  return created;
}

export async function enablePushNotifications(api: AuthenticatedApi): Promise<void> {
  const Notifications = await loadNotifications();
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("household-updates", {
      name: "Household updates",
      importance: Notifications.AndroidImportance.HIGH,
    });
  }
  const permission = await Notifications.requestPermissionsAsync();
  if (!permission.granted) throw new Error("Notification permission was not granted.");
  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  if (!projectId) {
    throw new Error("Push notifications need an EAS project ID before this build can register.");
  }
  const token = await Notifications.getExpoPushTokenAsync({ projectId });
  await api("/push/devices", {
    method: "PUT",
    body: JSON.stringify({
      installation_id: await installationId(),
      expo_push_token: token.data,
      platform: Platform.OS === "ios" ? "IOS" : "ANDROID",
    }),
  });
}

export async function disablePushNotifications(api: AuthenticatedApi): Promise<void> {
  await api("/push/devices", {
    method: "DELETE",
    body: JSON.stringify({ installation_id: await installationId() }),
  });
}
