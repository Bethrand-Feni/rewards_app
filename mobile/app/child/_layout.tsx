import { Ionicons } from "@expo/vector-icons";
import { Redirect, Tabs } from "expo-router";
import type { ColorValue } from "react-native";

import { useAuth } from "@/AuthContext";
import { colors } from "@/theme";

const icon = (name: keyof typeof Ionicons.glyphMap) =>
  function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <Ionicons name={name} color={color} size={size} />;
  };

export default function ChildLayout() {
  const { user } = useAuth();
  if (!user) return <Redirect href="/auth" />;
  if (!user.family_id || !user.role) return <Redirect href="/onboarding" />;
  if (user.role !== "CHILD") return <Redirect href="/parent" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.cocoa,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { position: "absolute", height: 78, paddingTop: 8, backgroundColor: colors.cream, borderTopColor: colors.border },
        tabBarLabelStyle: { fontWeight: "800", paddingBottom: 8, fontSize: 11 },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: icon("home-outline") }} />
      <Tabs.Screen name="chores" options={{ title: "Chores", tabBarIcon: icon("checkbox-outline") }} />
      <Tabs.Screen name="rewards" options={{ title: "Rewards", tabBarIcon: icon("gift-outline") }} />
      <Tabs.Screen name="settings" options={{ title: "Settings", tabBarIcon: icon("settings-outline") }} />
      <Tabs.Screen name="submit" options={{ href: null }} />
      <Tabs.Screen name="activity" options={{ href: null }} />
    </Tabs>
  );
}
