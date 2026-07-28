import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, Empty, Header, Loading, Pill, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Chore } from "@/types";

export default function Chores() {
  const { api } = useAuth();
  const chores = useQuery({ queryKey: ["chores"], queryFn: () => api<Chore[]>("/chores") });
  return (
    <Screen>
      <Header eyebrow="Earn points" title="Available chores" />
      {chores.isLoading ? <Loading /> : !chores.data?.length ? (
        <Empty title="Nothing waiting" message="Your parent hasn't added any available chores yet." />
      ) : chores.data.map((chore) => (
        <Card key={chore.id}>
          <View style={styles.row}>
            <View style={styles.icon}><Ionicons name={chore.mode === "ONE_TIME" ? "flash-outline" : "repeat-outline"} size={23} color={colors.cocoa} /></View>
            <View style={styles.grow}><Text style={styles.title}>{chore.title}</Text><Text style={styles.meta}>{chore.assigned_to_name ? `For ${chore.assigned_to_name}` : "Open to everyone"}</Text></View>
            <Pill label={`${chore.suggested_points} pts`} tone="success" />
          </View>
          <Text style={styles.description}>{chore.description || "Take a photo when you're finished."}</Text>
          <Pill label={chore.mode} tone="info" />
          <Button title="Submit this chore" onPress={() => router.push({ pathname: "/child/submit", params: { choreId: chore.id, title: chore.title } })} />
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  icon: { width: 48, height: 48, borderRadius: radius.sm, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  grow: { flex: 1 },
  title: { color: colors.cocoa, fontWeight: "900", fontSize: 17 },
  meta: { color: colors.muted, fontSize: 12, marginTop: 3 },
  description: { color: colors.cocoa, lineHeight: 20 },
});

