import * as SecureStore from "expo-secure-store";
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { makeAuthenticatedApi, publicApi, type AuthenticatedApi } from "./api";
import { disablePushNotifications } from "./notifications";
import type { AuthResponse, User } from "./types";

const SESSION_KEY = "sibling-rewards-session";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  api: AuthenticatedApi;
  accessToken: string | null;
  accountRegister: (input: {
    display_name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  accountLogin: (email: string, password: string) => Promise<void>;
  googleSignIn: () => Promise<void>;
  createHousehold: (family_name: string, timezone: string) => Promise<void>;
  joinHousehold: (family_code: string, join_pin: string) => Promise<void>;
  googleProof: () => Promise<{ google_id_token: string; nonce: string }>;
  refreshUser: () => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const sessionRef = useRef<AuthResponse | null>(null);

  const saveSession = useCallback(async (next: AuthResponse | null) => {
    const currentUser = sessionRef.current?.user;
    const nextUser = next?.user;
    const identityChanged =
      currentUser?.user_id !== nextUser?.user_id ||
      currentUser?.family_id !== nextUser?.family_id ||
      currentUser?.role !== nextUser?.role;

    if (identityChanged) queryClient.clear();
    sessionRef.current = next;
    setSession(next);
    if (next) await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(next));
    else await SecureStore.deleteItemAsync(SESSION_KEY);
  }, [queryClient]);

  const refresh = useCallback(async () => {
    const current = sessionRef.current;
    if (!current) return null;
    try {
      const next = await publicApi<AuthResponse>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: current.refresh_token }),
      });
      await saveSession(next);
      return next;
    } catch {
      await saveSession(null);
      return null;
    }
  }, [saveSession]);

  const api = useMemo(
    () => makeAuthenticatedApi(() => sessionRef.current?.access_token ?? null, refresh),
    [refresh],
  );

  useEffect(() => {
    SecureStore.getItemAsync(SESSION_KEY)
      .then(async (stored) => {
        if (!stored) return;
        const parsed = JSON.parse(stored) as AuthResponse;
        sessionRef.current = parsed;
        setSession(parsed);
        await refresh();
      })
      .catch(() => saveSession(null))
      .finally(() => setLoading(false));
  }, [refresh, saveSession]);

  const authenticate = useCallback(
    async (path: string, body: object) => {
      const next = await publicApi<AuthResponse>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      await saveSession(next);
    },
    [saveSession],
  );

  const updateMembership = useCallback(
    async (path: string, body: object) => {
      const next = await api<AuthResponse>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      await saveSession(next);
    },
    [api, saveSession],
  );

  const googleSignIn = useCallback(async (): Promise<void> => {
    const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
    if (!webClientId) {
      throw new Error("Google sign-in needs EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID in mobile/.env.");
    }
    const { nonce } = await publicApi<{ nonce: string }>("/auth/google/nonce", {
      method: "POST",
    });
    const google = await import("react-native-nitro-google-signin");
    google.GoogleOneTapSignIn.configure({ webClientId, nonce });
    await google.GoogleOneTapSignIn.checkPlayServices(true);
    let result = await google.GoogleOneTapSignIn.signIn();
    if (google.isNoSavedCredentialFoundResponse(result)) {
      result = await google.GoogleOneTapSignIn.createAccount();
    }
    if (google.isCancelledResponse(result)) throw new Error("Google sign-in was cancelled.");
    if (!google.isSuccessResponse(result) || !result.data.idToken) {
      throw new Error("Google did not return a usable sign-in token.");
    }
    const response = await publicApi<AuthResponse>("/auth/google", {
      method: "POST",
      body: JSON.stringify({ id_token: result.data.idToken, nonce }),
    });
    await saveSession(response);
  }, [saveSession]);

  const googleProof = useCallback(async () => {
    const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
    if (!webClientId) {
      throw new Error("Google sign-in needs EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID in mobile/.env.");
    }
    const { nonce } = await publicApi<{ nonce: string }>("/auth/google/nonce", {
      method: "POST",
    });
    const google = await import("react-native-nitro-google-signin");
    google.GoogleOneTapSignIn.configure({ webClientId, nonce });
    await google.GoogleOneTapSignIn.checkPlayServices(true);
    let result = await google.GoogleOneTapSignIn.signIn();
    if (google.isNoSavedCredentialFoundResponse(result)) {
      result = await google.GoogleOneTapSignIn.createAccount();
    }
    if (!google.isSuccessResponse(result) || !result.data.idToken) {
      throw new Error("Google confirmation was cancelled.");
    }
    return { google_id_token: result.data.idToken, nonce };
  }, []);

  const refreshUser = useCallback(async () => {
    const nextUser = await api<User>("/auth/me");
    const current = sessionRef.current;
    if (current) await saveSession({ ...current, user: nextUser });
    return nextUser;
  }, [api, saveSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      loading,
      api,
      accessToken: session?.access_token ?? null,
      accountRegister: (input) => authenticate("/auth/register", input),
      accountLogin: (email, password) => authenticate("/auth/login", { email, password }),
      createHousehold: (family_name, timezone) =>
        updateMembership("/households", { family_name, timezone }),
      joinHousehold: (family_code, join_pin) =>
        updateMembership("/households/join", { family_code, join_pin }),
      googleSignIn,
      googleProof,
      refreshUser,
      logout: async () => {
        const current = sessionRef.current;
        if (current) await disablePushNotifications(api).catch(() => undefined);
        await saveSession(null);
        if (current) {
          publicApi("/auth/logout", {
            method: "POST",
            body: JSON.stringify({ refresh_token: current.refresh_token }),
          }).catch(() => undefined);
        }
      },
    }),
    [
      api,
      authenticate,
      googleProof,
      googleSignIn,
      loading,
      refreshUser,
      saveSession,
      session?.access_token,
      session?.user,
      updateMembership,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
