import * as SecureStore from "expo-secure-store";
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
import type { AuthResponse, User } from "./types";

const SESSION_KEY = "sibling-rewards-session";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  api: AuthenticatedApi;
  accessToken: string | null;
  parentRegister: (input: {
    family_name: string;
    display_name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  parentLogin: (email: string, password: string) => Promise<void>;
  childLogin: (family_code: string, username: string, pin: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const sessionRef = useRef<AuthResponse | null>(null);

  const saveSession = useCallback(async (next: AuthResponse | null) => {
    sessionRef.current = next;
    setSession(next);
    if (next) await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(next));
    else await SecureStore.deleteItemAsync(SESSION_KEY);
  }, []);

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

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      loading,
      api,
      accessToken: session?.access_token ?? null,
      parentRegister: (input) => authenticate("/auth/parent/register", input),
      parentLogin: (email, password) => authenticate("/auth/parent/login", { email, password }),
      childLogin: (family_code, username, pin) =>
        authenticate("/auth/child/login", { family_code, username, pin }),
      logout: async () => {
        const current = sessionRef.current;
        await saveSession(null);
        if (current) {
          publicApi("/auth/logout", {
            method: "POST",
            body: JSON.stringify({ refresh_token: current.refresh_token }),
          }).catch(() => undefined);
        }
      },
    }),
    [api, authenticate, loading, saveSession, session?.access_token, session?.user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
