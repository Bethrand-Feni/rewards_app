import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, Empty, Header, Loading, Pill, Screen } from "@/components";
import { colors, spacing } from "@/theme";
import type { PointTransaction, Redemption, Submission } from "@/types";

function statusTone(status: string): "success" | "danger" | "info" | "neutral" {
  if (status === "APPROVED") return "success";
  if (status === "REJECTED") return "danger";
  if (status === "CHANGES_REQUESTED") return "info";
  return "neutral";
}

export default function ChildActivity() {
  const { api } = useAuth();
  const submissions = useQuery({ queryKey: ["submissions", "mine"], queryFn: () => api<Submission[]>("/submissions/mine") });
  const redemptions = useQuery({ queryKey: ["redemptions", "mine"], queryFn: () => api<Redemption[]>("/redemptions/mine") });
  const history = useQuery({ queryKey: ["points", "history"], queryFn: () => api<PointTransaction[]>("/points/history") });

  if (submissions.isLoading || redemptions.isLoading || history.isLoading)
    return <Screen><Header title="Activity" /><Loading /></Screen>;

  return (
    <Screen>
      <Header eyebrow="Your progress" title="Activity" />
      <Text style={styles.section}>Submissions</Text>
      {!submissions.data?.length ? <Empty title="No submissions yet" message="Complete a chore or submit something helpful to get started." /> : submissions.data.map((item) => (
        <Card key={item.id}>
          <View style={styles.row}>
            <View style={styles.grow}><Text style={styles.title}>{item.title}</Text><Text style={styles.date}>{new Date(item.created_at).toLocaleString()}</Text></View>
            <Pill label={item.status} tone={statusTone(item.status)} />
          </View>
          {item.awarded_points ? <Text style={styles.earned}>+{item.awarded_points} points</Text> : null}
          {item.review_comment ? <Text style={styles.comment}>Parent note: {item.review_comment}</Text> : null}
          {item.status === "CHANGES_REQUESTED" ? <Button title="Update proof" onPress={() => router.push({ pathname: "/child/submit", params: { submissionId: item.id, title: item.title } })} /> : null}
        </Card>
      ))}

      <Text style={styles.section}>Reward requests</Text>
      {!redemptions.data?.length ? <Empty title="No reward requests" message="Affordable rewards can be requested from the reward pool." /> : redemptions.data.map((item) => (
        <Card key={item.id}>
          <View style={styles.row}><View style={styles.grow}><Text style={styles.title}>{item.reward_name}</Text><Text style={styles.date}>{item.point_cost_snapshot} points</Text></View><Pill label={item.status} tone={statusTone(item.status)} /></View>
          {item.review_comment ? <Text style={styles.comment}>Parent note: {item.review_comment}</Text> : null}
        </Card>
      ))}

      <Text style={styles.section}>Points ledger</Text>
      {!history.data?.length ? <Empty title="No point activity" message="Every earned and spent point will be recorded here." /> : history.data.map((item) => (
        <Card key={item.id} style={styles.transaction}>
          <View style={styles.grow}><Text style={styles.title}>{item.reason}</Text><Text style={styles.date}>{new Date(item.created_at).toLocaleString()}</Text></View>
          <Text style={[styles.amount, item.amount < 0 && styles.negative]}>{item.amount > 0 ? "+" : ""}{item.amount}</Text>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  section: { color: colors.cocoa, fontWeight: "900", fontSize: 20, marginTop: spacing.sm },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  grow: { flex: 1 },
  title: { color: colors.cocoa, fontWeight: "900" },
  date: { color: colors.muted, fontSize: 12, marginTop: 4 },
  earned: { color: colors.success, fontWeight: "900", fontSize: 18 },
  comment: { color: colors.info, lineHeight: 20, backgroundColor: "#E7F1F4", padding: 10, borderRadius: 8 },
  transaction: { flexDirection: "row", alignItems: "center" },
  amount: { color: colors.success, fontWeight: "900", fontSize: 21 },
  negative: { color: colors.danger },
});

