import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, Header, Loading, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Child, Redemption, Submission } from "@/types";

export default function ParentHome() {
  const { api, logout, user } = useAuth();
  const submissions = useQuery({
    queryKey: ["submissions", "pending"],
    queryFn: () => api<Submission[]>("/submissions/pending"),
  });
  const redemptions = useQuery({
    queryKey: ["redemptions", "pending"],
    queryFn: () => api<Redemption[]>("/redemptions/pending"),
  });
  const children = useQuery({
    queryKey: ["children"],
    queryFn: () => api<Child[]>("/household/children"),
  });
  const loading = submissions.isLoading || redemptions.isLoading || children.isLoading;

  return (
    <Screen>
      <Header
        eyebrow={user?.family_name}
        title={`Hi, ${user?.display_name}`}
        action={<Button title="Log out" variant="ghost" onPress={logout} />}
      />
      {loading ? (
        <Loading />
      ) : (
        <>
          <Card style={styles.hero}>
            <View style={styles.heroIcon}><Ionicons name="sparkles" size={28} color={colors.cocoa} /></View>
            <View style={styles.heroText}>
              <Text style={styles.heroTitle}>Household code</Text>
              <Text style={styles.code}>{user?.family_code}</Text>
              <Text style={styles.muted}>Children use this with their username and PIN.</Text>
            </View>
          </Card>

          <View style={styles.stats}>
            <Stat value={submissions.data?.length ?? 0} label="Chores to review" color={colors.sun} />
            <Stat value={redemptions.data?.length ?? 0} label="Reward requests" color={colors.blush} />
            <Stat value={children.data?.filter((child) => child.is_active).length ?? 0} label="Active children" color="#CFE5D5" />
          </View>

          <Text style={styles.sectionTitle}>What needs attention</Text>
          <Card>
            <Row icon="camera-outline" label="Pending activity proof" value={submissions.data?.length ?? 0} />
            <View style={styles.rule} />
            <Row icon="gift-outline" label="Pending reward requests" value={redemptions.data?.length ?? 0} />
          </Card>
        </>
      )}
    </Screen>
  );
}

function Stat({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <View style={[styles.stat, { backgroundColor: color }]}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function Row({ icon, label, value }: { icon: keyof typeof Ionicons.glyphMap; label: string; value: number }) {
  return (
    <View style={styles.row}>
      <Ionicons name={icon} color={colors.peach} size={22} />
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { backgroundColor: colors.sun, flexDirection: "row", padding: spacing.lg, alignItems: "center" },
  heroIcon: { width: 54, height: 54, borderRadius: 18, backgroundColor: "rgba(255,255,255,.45)", alignItems: "center", justifyContent: "center" },
  heroText: { flex: 1, gap: 3 },
  heroTitle: { color: colors.cocoa, fontWeight: "800" },
  code: { color: colors.cocoa, fontSize: 28, letterSpacing: 5, fontWeight: "900" },
  muted: { color: colors.muted, fontSize: 12 },
  stats: { flexDirection: "row", gap: spacing.sm },
  stat: { flex: 1, minHeight: 118, borderRadius: radius.md, padding: 14, justifyContent: "space-between" },
  statValue: { color: colors.cocoa, fontWeight: "900", fontSize: 30 },
  statLabel: { color: colors.cocoa, fontWeight: "800", fontSize: 12 },
  sectionTitle: { color: colors.cocoa, fontWeight: "900", fontSize: 19, marginTop: spacing.sm },
  row: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: spacing.md },
  rowLabel: { color: colors.cocoa, flex: 1, fontWeight: "700" },
  rowValue: { width: 32, height: 32, borderRadius: 16, overflow: "hidden", backgroundColor: colors.canvas, color: colors.cocoa, fontWeight: "900", textAlign: "center", lineHeight: 32 },
  rule: { height: 1, backgroundColor: colors.border },
});

