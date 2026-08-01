import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { AnimatedNumber, Button, Card, ErrorText, Header, Loading, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Child, Redemption, Submission } from "@/types";

export default function ParentHome() {
  const { api, user } = useAuth();
  const submissions = useQuery({
    queryKey: ["family", user?.family_id, "submissions", "pending"],
    queryFn: () => api<Submission[]>("/submissions/pending"),
    refetchInterval: 30_000,
  });
  const redemptions = useQuery({
    queryKey: ["family", user?.family_id, "redemptions", "pending"],
    queryFn: () => api<Redemption[]>("/redemptions/pending"),
    refetchInterval: 30_000,
  });
  const children = useQuery({
    queryKey: ["family", user?.family_id, "children"],
    queryFn: () => api<Child[]>("/household/children"),
  });
  const loading = submissions.isLoading || redemptions.isLoading || children.isLoading;
  const loadError = submissions.error ?? redemptions.error ?? children.error;
  const retry = () => {
    void Promise.all([submissions.refetch(), redemptions.refetch(), children.refetch()]);
  };

  return (
    <Screen>
      <Header eyebrow={user?.family_name} title={`Hi, ${user?.display_name}`} />
      {loading ? (
        <Loading />
      ) : loadError ? (
        <Card>
          <ErrorText message={loadError.message || "Could not load the household dashboard."} />
          <Button title="Try again" variant="secondary" onPress={retry} />
        </Card>
      ) : (
        <>
          <Card style={styles.hero}>
            <View style={styles.heroIcon}><Ionicons name="sparkles" size={28} color={colors.cocoa} /></View>
            <View style={styles.heroText}>
              <Text style={styles.heroTitle}>Household code</Text>
              <Text style={styles.code}>{user?.family_code}</Text>
              <Text style={styles.muted}>Members use this with the one-time code from their invitation.</Text>
            </View>
          </Card>

          <View style={styles.stats}>
            <Stat
              value={submissions.data?.length ?? 0}
              label="Chores to review"
              color={colors.sun}
              onPress={() => router.push({ pathname: "/parent/reviews", params: { focus: "submissions" } })}
            />
            <Stat
              value={redemptions.data?.length ?? 0}
              label="Reward requests"
              color={colors.blush}
              onPress={() => router.push({ pathname: "/parent/reviews", params: { focus: "redemptions" } })}
            />
            <Stat
              value={children.data?.filter((child) => child.is_active).length ?? 0}
              label="Active children"
              color="#CFE5D5"
              onPress={() => router.push("/parent/manage")}
            />
          </View>

          <Text style={styles.sectionTitle}>What needs attention</Text>
          <Card>
            <Row
              icon="camera-outline"
              label="Pending activity proof"
              value={submissions.data?.length ?? 0}
              onPress={() => router.push({ pathname: "/parent/reviews", params: { focus: "submissions" } })}
            />
            <View style={styles.rule} />
            <Row
              icon="gift-outline"
              label="Pending reward requests"
              value={redemptions.data?.length ?? 0}
              onPress={() => router.push({ pathname: "/parent/reviews", params: { focus: "redemptions" } })}
            />
          </Card>
          <Button title="View household activity" icon="time-outline" variant="secondary" onPress={() => router.push("/parent/activity")} />
        </>
      )}
    </Screen>
  );
}

function Stat({
  value,
  label,
  color,
  onPress,
}: {
  value: number;
  label: string;
  color: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${label}: ${value}. Open`}
      onPress={onPress}
      style={({ pressed }) => [styles.stat, { backgroundColor: color }, pressed && styles.pressed]}
    >
      <AnimatedNumber value={value} style={styles.statValue} />
      <Text style={styles.statLabel}>{label}</Text>
    </Pressable>
  );
}

function Row({
  icon,
  label,
  value,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: number;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${label}: ${value}. Open reviews`}
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <Ionicons name={icon} color={colors.peach} size={22} />
      <Text style={styles.rowLabel}>{label}</Text>
      <View style={styles.rowValue}>
        <AnimatedNumber value={value} style={styles.rowValueText} />
      </View>
    </Pressable>
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
  rowValue: { width: 32, height: 32, borderRadius: 16, overflow: "hidden", backgroundColor: colors.canvas, alignItems: "center", justifyContent: "center" },
  rowValueText: { color: colors.cocoa, fontWeight: "900" },
  rule: { height: 1, backgroundColor: colors.border },
  pressed: { opacity: 0.68, transform: [{ scale: 0.98 }] },
});
