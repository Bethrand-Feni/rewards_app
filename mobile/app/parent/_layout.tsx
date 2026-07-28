import { Ionicons } from "@expo/vector-icons";
import { Redirect, Tabs } from "expo-router";
import type { ColorValue } from "react-native";

import { useAuth } from "@/AuthContext";
import { colors } from "@/theme";

const icon = (name: keyof typeof Ionicons.glyphMap) =>
  function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <Ionicons name={name} color={color} size={size} />;
  };

export default function ParentLayout() {
  const { user } = useAuth();
  if (!user) return <Redirect href="/auth" />;
  if (user.role !== "PARENT") return <Redirect href="/child" />;
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
      <Tabs.Screen name="reviews" options={{ title: "Reviews", tabBarIcon: icon("checkmark-done-outline") }} />
      <Tabs.Screen name="manage" options={{ title: "Manage", tabBarIcon: icon("grid-outline") }} />
      <Tabs.Screen name="activity" options={{ title: "Activity", tabBarIcon: icon("time-outline") }} />
    </Tabs>
  );
}
