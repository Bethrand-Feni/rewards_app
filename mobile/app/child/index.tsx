import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { rewardImageUrl } from "@/api";
import { AnimatedNumber, Button, Card, Empty, Header, Loading, Pill, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Chore, Reward, Submission } from "@/types";

export default function ChildHome() {
  const { api, accessToken, user } = useAuth();
  const balance = useQuery({ queryKey: ["points", "balance"], queryFn: () => api<{ balance: number }>("/points/balance"), refetchInterval: 30_000 });
  const chores = useQuery({ queryKey: ["chores"], queryFn: () => api<Chore[]>("/chores"), refetchInterval: 30_000 });
  const rewards = useQuery({ queryKey: ["rewards"], queryFn: () => api<Reward[]>("/rewards"), refetchInterval: 30_000 });
  const submissions = useQuery({ queryKey: ["submissions", "mine"], queryFn: () => api<Submission[]>("/submissions/mine"), refetchInterval: 30_000 });
  const loading = balance.isLoading || chores.isLoading || rewards.isLoading || submissions.isLoading;
  const points = balance.data?.balance ?? 0;
  const affordable = rewards.data?.filter((reward) => reward.point_cost <= points) ?? [];
  const pending = submissions.data?.filter((item) => item.status === "PENDING").length ?? 0;

  return (
    <Screen>
      <Header eyebrow={user?.family_name} title={`Hey, ${user?.display_name}!`} />
      {loading ? <Loading /> : (
        <>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Your balance is ${points} points. Open activity`}
            onPress={() => router.push("/child/activity")}
            style={({ pressed }) => pressed && styles.pressed}
          >
            <Card style={styles.balanceCard}>
              <View>
                <Text style={styles.balanceLabel}>Your balance</Text>
                <AnimatedNumber value={points} style={styles.balance} />
                <Text style={styles.points}>points</Text>
              </View>
              <View style={styles.star}><Ionicons name="star" size={38} color={colors.cocoa} /></View>
            </Card>
          </Pressable>
          <View style={styles.stats}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${pending} submissions waiting for review. Open activity`}
              onPress={() => router.push("/child/activity")}
              style={({ pressed }) => [styles.statPressable, pressed && styles.pressed]}
            >
              <Card style={styles.stat}><AnimatedNumber value={pending} style={styles.statValue} /><Text style={styles.statLabel}>Waiting for review</Text></Card>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${chores.data?.length ?? 0} available chores. Open chores`}
              onPress={() => router.push("/child/chores")}
              style={({ pressed }) => [styles.statPressable, pressed && styles.pressed]}
            >
              <Card style={styles.stat}><AnimatedNumber value={chores.data?.length ?? 0} style={styles.statValue} /><Text style={styles.statLabel}>Available chores</Text></Card>
            </Pressable>
          </View>
          <Button title="View activity history" icon="time-outline" variant="secondary" onPress={() => router.push("/child/activity")} />
          <Button title="Submit an activity" icon="camera-outline" onPress={() => router.push("/child/submit")} />
          <Text style={styles.section}>Rewards you can afford</Text>
          {!affordable.length ? <Empty title="Keep going" message="Complete more activities to unlock your first reward." /> : affordable.slice(0, 3).map((reward) => (
            <Pressable
              key={reward.id}
              accessibilityRole="button"
              accessibilityLabel={`${reward.name}, ${reward.point_cost} points. Open rewards`}
              onPress={() => router.push("/child/rewards")}
              style={({ pressed }) => pressed && styles.pressed}
            >
              <Card style={styles.reward}>
                {reward.has_image ? <Image source={{ uri: rewardImageUrl(reward.id), headers: { Authorization: `Bearer ${accessToken}` } }} style={styles.rewardImage} /> : <View style={styles.rewardIcon}><Ionicons name="gift-outline" size={24} color={colors.cocoa} /></View>}
                <View style={styles.grow}><Text style={styles.rewardName}>{reward.name}</Text><Text style={styles.meta}>{reward.description}</Text></View>
                <Pill label={`${reward.point_cost} pts`} tone="success" />
              </Card>
            </Pressable>
          ))}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  balanceCard: { minHeight: 170, backgroundColor: colors.sun, padding: spacing.lg, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  balanceLabel: { color: colors.cocoa, fontWeight: "800", fontSize: 15 },
  balance: { color: colors.cocoa, fontWeight: "900", fontSize: 56, lineHeight: 60 },
  points: { color: colors.cocoa, fontWeight: "800" },
  star: { width: 84, height: 84, borderRadius: 30, backgroundColor: "rgba(255,255,255,.4)", alignItems: "center", justifyContent: "center", transform: [{ rotate: "8deg" }] },
  stats: { flexDirection: "row", gap: spacing.sm },
  statPressable: { flex: 1 },
  stat: { flex: 1, minHeight: 110, justifyContent: "space-between" },
  statValue: { color: colors.cocoa, fontWeight: "900", fontSize: 30 },
  statLabel: { color: colors.muted, fontWeight: "700" },
  section: { color: colors.cocoa, fontWeight: "900", fontSize: 20, marginTop: spacing.sm },
  reward: { flexDirection: "row", alignItems: "center" },
  rewardIcon: { width: 48, height: 48, borderRadius: radius.sm, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  rewardImage: { width: 48, height: 48, borderRadius: radius.sm, backgroundColor: colors.border },
  grow: { flex: 1 },
  rewardName: { color: colors.cocoa, fontWeight: "900" },
  meta: { color: colors.muted, marginTop: 3 },
  pressed: { opacity: 0.68, transform: [{ scale: 0.98 }] },
});
