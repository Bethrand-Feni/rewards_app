import { useQueryClient } from "@tanstack/react-query";
import { PropsWithChildren, useEffect, useMemo, useRef, useState } from "react";
import { AppState, StyleSheet, Text, View } from "react-native";

import { useAuth } from "./AuthContext";
import { RealtimeClient, type RealtimeEvent } from "./realtime";
import { colors, radius, spacing } from "./theme";

const INVALIDATION_SEGMENTS: Record<RealtimeEvent["type"], string[]> = {
  "submission.created": ["submissions"],
  "submission.updated": ["submissions"],
  "points.changed": ["points", "submissions"],
  "redemption.created": ["redemptions"],
  "redemption.updated": ["redemptions", "rewards"],
  "chores.changed": ["chores"],
  "rewards.changed": ["rewards"],
  "children.changed": ["children"],
};

const EVENT_MESSAGES: Record<RealtimeEvent["type"], string> = {
  "submission.created": "New activity is ready to review.",
  "submission.updated": "Your activity review was updated.",
  "points.changed": "Your points balance was updated.",
  "redemption.created": "A new reward request is ready to review.",
  "redemption.updated": "Your reward request was updated.",
  "chores.changed": "The household chore list was updated.",
  "rewards.changed": "The reward pool was updated.",
  "children.changed": "The household profiles were updated.",
};

export function RealtimeProvider({ children }: PropsWithChildren) {
  const { api, user } = useAuth();
  const queryClient = useQueryClient();
  const [banner, setBanner] = useState("");
  const appActive = useRef(AppState.currentState === "active");

  const onEvent = useMemo(
    () => async (event: RealtimeEvent) => {
      const segments = INVALIDATION_SEGMENTS[event.type];
      const matchesEvent = (queryKey: readonly unknown[]) =>
        segments.some((segment) => queryKey.includes(segment));
      const predicate = (query: { queryKey: readonly unknown[] }) =>
        matchesEvent(query.queryKey);
      const previousBalance = queryClient
        .getQueriesData<{ balance: number }>({ queryKey: ["points", "balance"] })
        .find(([, data]) => data)?.[1]?.balance;

      try {
        await queryClient.invalidateQueries({ predicate, refetchType: "none" });
        const hasVisibleQuery = queryClient
          .getQueryCache()
          .findAll({ predicate })
          .some((query) => query.isActive());
        if (!hasVisibleQuery) return;
        await queryClient.refetchQueries(
          { predicate, type: "active" },
          { throwOnError: true },
        );

        let message = EVENT_MESSAGES[event.type];
        if (event.type === "points.changed" && previousBalance !== undefined) {
          const nextBalance = queryClient
            .getQueriesData<{ balance: number }>({ queryKey: ["points", "balance"] })
            .find(([, data]) => data)?.[1]?.balance;
          const difference = nextBalance === undefined ? 0 : nextBalance - previousBalance;
          if (difference > 0) message = `Chore approved — ${difference} points added!`;
          if (difference < 0) message = `Reward approved — ${Math.abs(difference)} points used.`;
        }
        setBanner(message);
      } catch {
        // A failed refetch should not show confirmation for unconfirmed server state.
      }
    },
    [queryClient],
  );

  useEffect(() => {
    if (!banner) return;
    const timer = setTimeout(() => setBanner(""), 4_000);
    return () => clearTimeout(timer);
  }, [banner]);

  useEffect(() => {
    if (!user?.family_id || !user.role) return;
    const client = new RealtimeClient(api, (event) => void onEvent(event));
    if (appActive.current) client.start();
    const subscription = AppState.addEventListener("change", (state) => {
      appActive.current = state === "active";
      if (appActive.current) client.start();
      else client.stop();
    });
    return () => {
      subscription.remove();
      client.stop();
    };
  }, [api, onEvent, user?.family_id, user?.role, user?.user_id]);

  return (
    <View style={styles.root}>
      {children}
      {banner ? (
        <View accessibilityLiveRegion="polite" style={styles.banner}>
          <Text style={styles.bannerText}>{banner}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  banner: {
    position: "absolute",
    top: 52,
    left: spacing.md,
    right: spacing.md,
    zIndex: 100,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.peach,
    backgroundColor: "#FFF0DF",
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    shadowColor: colors.cocoa,
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
  bannerText: { color: colors.cocoa, fontWeight: "900", textAlign: "center" },
});
