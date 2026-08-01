import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { rewardImageUrl } from "@/api";
import { Button, Card, Empty, ErrorText, FeedbackBanner, Header, Loading, Pill, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Redemption, Reward } from "@/types";

export default function Rewards() {
  const { api, accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const balance = useQuery({ queryKey: ["points", "balance"], queryFn: () => api<{ balance: number }>("/points/balance") });
  const rewards = useQuery({ queryKey: ["rewards"], queryFn: () => api<Reward[]>("/rewards") });
  const redemptions = useQuery({ queryKey: ["redemptions", "mine"], queryFn: () => api<Redemption[]>("/redemptions/mine") });
  const request = useMutation({
    mutationFn: (rewardId: string) => api(`/rewards/${rewardId}/redemptions`, { method: "POST" }),
    onMutate: () => setSuccess(""),
    onSuccess: async () => {
      setError("");
      setSuccess("Reward request sent — your parent can review it now.");
      await queryClient.invalidateQueries({ queryKey: ["redemptions"] });
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "Could not request reward"),
  });
  const points = balance.data?.balance ?? 0;
  const pendingIds = new Set(redemptions.data?.filter((item) => item.status === "PENDING").map((item) => item.reward_id));

  return (
    <Screen>
      <Header eyebrow={`${points} points available`} title="Reward pool" />
      <ErrorText message={error} />
      <FeedbackBanner message={success} />
      {rewards.isLoading || balance.isLoading ? <Loading /> : !rewards.data?.length ? (
        <Empty title="No rewards yet" message="Your parent is still putting together the reward pool." />
      ) : rewards.data.map((reward, index) => {
        const affordable = points >= reward.point_cost;
        const pending = pendingIds.has(reward.id);
        return (
          <Card key={reward.id} style={styles.card}>
            {reward.has_image ? (
              <Image source={{ uri: rewardImageUrl(reward.id), headers: { Authorization: `Bearer ${accessToken}` } }} style={styles.art} />
            ) : (
              <View style={[styles.art, { backgroundColor: index % 2 ? colors.blush : colors.sun }]}>
                <Ionicons name={index % 3 === 0 ? "film-outline" : index % 3 === 1 ? "game-controller-outline" : "gift-outline"} size={42} color={colors.cocoa} />
              </View>
            )}
            <Text style={styles.title}>{reward.name}</Text>
            <Text style={styles.body}>{reward.description || "A household reward worth saving for."}</Text>
            <View style={styles.row}>
              <Pill label={`${reward.point_cost} points`} tone={affordable ? "success" : "neutral"} />
              <Text style={styles.remaining}>{affordable ? `${points - reward.point_cost} left after approval` : `${reward.point_cost - points} more needed`}</Text>
            </View>
            <Button title={pending ? "Request pending" : affordable ? "Request reward" : "Not enough points yet"} disabled={!affordable || pending} loading={request.isPending && request.variables === reward.id} onPress={() => request.mutate(reward.id)} />
          </Card>
        );
      })}
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { overflow: "hidden" },
  art: { height: 120, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  title: { color: colors.cocoa, fontWeight: "900", fontSize: 20 },
  body: { color: colors.muted, lineHeight: 20 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  remaining: { color: colors.muted, fontSize: 12, flex: 1, textAlign: "right" },
});
