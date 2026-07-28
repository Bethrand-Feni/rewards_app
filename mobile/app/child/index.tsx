import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, Empty, Header, Loading, Pill, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Chore, Reward, Submission } from "@/types";

export default function ChildHome() {
  const { api, logout, user } = useAuth();
  const balance = useQuery({ queryKey: ["points", "balance"], queryFn: () => api<{ balance: number }>("/points/balance") });
  const chores = useQuery({ queryKey: ["chores"], queryFn: () => api<Chore[]>("/chores") });
  const rewards = useQuery({ queryKey: ["rewards"], queryFn: () => api<Reward[]>("/rewards") });
  const submissions = useQuery({ queryKey: ["submissions", "mine"], queryFn: () => api<Submission[]>("/submissions/mine") });
  const loading = balance.isLoading || chores.isLoading || rewards.isLoading || submissions.isLoading;
  const points = balance.data?.balance ?? 0;
  const affordable = rewards.data?.filter((reward) => reward.point_cost <= points) ?? [];
  const pending = submissions.data?.filter((item) => item.status === "PENDING").length ?? 0;

  return (
    <Screen>
      <Header eyebrow={user?.family_name} title={`Hey, ${user?.display_name}!`} action={<Button title="Log out" variant="ghost" onPress={logout} />} />
      {loading ? <Loading /> : (
        <>
          <Card style={styles.balanceCard}>
            <View>
              <Text style={styles.balanceLabel}>Your balance</Text>
              <Text style={styles.balance}>{points}</Text>
              <Text style={styles.points}>points</Text>
            </View>
            <View style={styles.star}><Ionicons name="star" size={38} color={colors.cocoa} /></View>
          </Card>
          <View style={styles.stats}>
            <Card style={styles.stat}><Text style={styles.statValue}>{pending}</Text><Text style={styles.statLabel}>Waiting for review</Text></Card>
            <Card style={styles.stat}><Text style={styles.statValue}>{chores.data?.length ?? 0}</Text><Text style={styles.statLabel}>Available chores</Text></Card>
          </View>
          <Button title="Submit an activity" icon="camera-outline" onPress={() => router.push("/child/submit")} />
          <Text style={styles.section}>Rewards you can afford</Text>
          {!affordable.length ? <Empty title="Keep going" message="Complete more activities to unlock your first reward." /> : affordable.slice(0, 3).map((reward) => (
            <Card key={reward.id} style={styles.reward}>
              <View style={styles.rewardIcon}><Ionicons name="gift-outline" size={24} color={colors.cocoa} /></View>
              <View style={styles.grow}><Text style={styles.rewardName}>{reward.name}</Text><Text style={styles.meta}>{reward.description}</Text></View>
              <Pill label={`${reward.point_cost} pts`} tone="success" />
            </Card>
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
  stat: { flex: 1, minHeight: 110, justifyContent: "space-between" },
  statValue: { color: colors.cocoa, fontWeight: "900", fontSize: 30 },
  statLabel: { color: colors.muted, fontWeight: "700" },
  section: { color: colors.cocoa, fontWeight: "900", fontSize: 20, marginTop: spacing.sm },
  reward: { flexDirection: "row", alignItems: "center" },
  rewardIcon: { width: 48, height: 48, borderRadius: radius.sm, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  grow: { flex: 1 },
  rewardName: { color: colors.cocoa, fontWeight: "900" },
  meta: { color: colors.muted, marginTop: 3 },
});

