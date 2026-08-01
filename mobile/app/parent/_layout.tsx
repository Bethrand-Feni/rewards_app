import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { Redirect, Tabs } from "expo-router";
import type { ColorValue } from "react-native";

import { useAuth } from "@/AuthContext";
import { colors } from "@/theme";
import type { Redemption, Submission } from "@/types";

const icon = (name: keyof typeof Ionicons.glyphMap) =>
  function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <Ionicons name={name} color={color} size={size} />;
  };

export default function ParentLayout() {
  const { api, user } = useAuth();
  const submissions = useQuery({
    queryKey: ["family", user?.family_id, "submissions", "pending"],
    queryFn: () => api<Submission[]>("/submissions/pending"),
    enabled: user?.role === "PARENT",
    refetchInterval: 30_000,
  });
  const redemptions = useQuery({
    queryKey: ["family", user?.family_id, "redemptions", "pending"],
    queryFn: () => api<Redemption[]>("/redemptions/pending"),
    enabled: user?.role === "PARENT",
    refetchInterval: 30_000,
  });
  const reviewCount = (submissions.data?.length ?? 0) + (redemptions.data?.length ?? 0);
  if (!user) return <Redirect href="/auth" />;
  if (!user.family_id || !user.role) return <Redirect href="/onboarding" />;
  if (user.role !== "PARENT") return <Redirect href="/child" />;
  if (user.deletion_scheduled_for) return <Redirect href={"/settings" as never} />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.cocoa,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          position: "absolute",
          height: 78,
          paddingTop: 8,
          backgroundColor: colors.cream,
          borderTopColor: colors.border,
        },
        tabBarLabelStyle: { fontWeight: "800", paddingBottom: 8 },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: icon("home-outline") }} />
      <Tabs.Screen name="reviews" options={{ title: "Reviews", tabBarIcon: icon("checkmark-done-outline"), tabBarBadge: reviewCount || undefined, tabBarBadgeStyle: { backgroundColor: colors.peach, color: colors.cocoa, fontWeight: "900" } }} />
      <Tabs.Screen name="manage" options={{ title: "Manage", tabBarIcon: icon("grid-outline") }} />
      <Tabs.Screen name="settings" options={{ title: "Settings", tabBarIcon: icon("settings-outline") }} />
      <Tabs.Screen name="activity" options={{ href: null }} />
    </Tabs>
  );
}
