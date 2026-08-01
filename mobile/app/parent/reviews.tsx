import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { submissionImageUrl } from "@/api";
import { Button, Card, Empty, ErrorText, Field, Header, Loading, Pill, Screen } from "@/components";
import { colors, spacing } from "@/theme";
import type { Redemption, Submission } from "@/types";

export default function Reviews() {
  const { focus } = useLocalSearchParams<{ focus?: "submissions" | "redemptions" }>();
  const { api, accessToken, user } = useAuth();
  const queryClient = useQueryClient();
  const scrollRef = useRef<ScrollView>(null);
  const sectionOffsets = useRef({ submissions: 0, redemptions: 0 });
  const [points, setPoints] = useState<Record<string, string>>({});
  const [comments, setComments] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
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
  const action = useMutation({
    mutationFn: ({ key: _key, path, body }: { key: string; path: string; body: object }) =>
      api(path, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries();
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "Review failed"),
  });

  useEffect(() => {
    if (!focus || submissions.isLoading || redemptions.isLoading) return;
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        y: Math.max(0, sectionOffsets.current[focus] - 12),
        animated: true,
      });
    });
  }, [focus, redemptions.isLoading, submissions.isLoading]);

  if (submissions.isLoading || redemptions.isLoading)
    return <Screen><Header title="Reviews" /><Loading /></Screen>;

  const scrollToSection = (section: "submissions" | "redemptions", y: number) => {
    sectionOffsets.current[section] = y;
    if (focus === section) {
      requestAnimationFrame(() => scrollRef.current?.scrollTo({ y: Math.max(0, y - 12), animated: true }));
    }
  };

  return (
    <Screen scrollRef={scrollRef}>
      <Header eyebrow="Parent queue" title="Reviews" />
      <ErrorText message={error} />
      <View onLayout={(event) => scrollToSection("submissions", event.nativeEvent.layout.y)}>
        <Text style={styles.section}>Activity proof</Text>
      </View>
      {submissions.isError ? (
        <LoadError
          message={queryErrorMessage(submissions.error, "Could not load activity submissions.")}
          onRetry={() => void submissions.refetch()}
        />
      ) : !submissions.data?.length ? (
        <Empty title="All caught up" message="New activity submissions will appear here." />
      ) : (
        submissions.data.map((item) => (
          <Card key={item.id}>
            <Image
              source={{ uri: submissionImageUrl(item.id), headers: { Authorization: `Bearer ${accessToken}` } }}
              style={styles.image}
            />
            <View style={styles.titleRow}>
              <View style={styles.grow}>
                <Text style={styles.title}>{item.title}</Text>
                <Text style={styles.meta}>{item.child_name} · {new Date(item.created_at).toLocaleDateString()}</Text>
              </View>
              <Pill label={item.submission_type} tone="info" />
            </View>
            {item.description ? <Text style={styles.body}>{item.description}</Text> : null}
            <Field
              label="Points to award"
              keyboardType="number-pad"
              value={points[item.id] ?? String(item.suggested_points ?? 10)}
              onChangeText={(value) => setPoints((current) => ({ ...current, [item.id]: value }))}
            />
            <Field
              label="Comment (required for changes)"
              value={comments[item.id] ?? ""}
              onChangeText={(value) => setComments((current) => ({ ...current, [item.id]: value }))}
            />
            <Button
              title="Approve"
              icon="checkmark-circle-outline"
              loading={action.isPending && action.variables?.key === `approve-submission-${item.id}`}
              onPress={() =>
                action.mutate({
                  key: `approve-submission-${item.id}`,
                  path: `/submissions/${item.id}/approve`,
                  body: { awarded_points: Number(points[item.id] ?? item.suggested_points ?? 10) },
                })
              }
            />
            <View style={styles.actions}>
              <View style={styles.grow}>
                <Button
                  title="Request changes"
                  variant="secondary"
                  disabled={(comments[item.id] ?? "").trim().length < 2}
                  loading={action.isPending && action.variables?.key === `changes-submission-${item.id}`}
                  onPress={() => action.mutate({ key: `changes-submission-${item.id}`, path: `/submissions/${item.id}/request-changes`, body: { comment: comments[item.id] ?? "" } })}
                />
              </View>
              <View style={styles.grow}>
                <Button
                  title="Reject"
                  variant="danger"
                  loading={action.isPending && action.variables?.key === `reject-submission-${item.id}`}
                  onPress={() => action.mutate({ key: `reject-submission-${item.id}`, path: `/submissions/${item.id}/reject`, body: { comment: comments[item.id] ?? "" } })}
                />
              </View>
            </View>
          </Card>
        ))
      )}

      <View onLayout={(event) => scrollToSection("redemptions", event.nativeEvent.layout.y)}>
        <Text style={styles.section}>Reward requests</Text>
      </View>
      {redemptions.isError ? (
        <LoadError
          message={queryErrorMessage(redemptions.error, "Could not load reward requests.")}
          onRetry={() => void redemptions.refetch()}
        />
      ) : !redemptions.data?.length ? (
        <Empty title="No reward requests" message="Requests children can afford will appear here." />
      ) : (
        redemptions.data.map((item) => (
          <Card key={item.id}>
            <View style={styles.titleRow}>
              <View style={styles.grow}>
                <Text style={styles.title}>{item.reward_name}</Text>
                <Text style={styles.meta}>{item.child_name}</Text>
              </View>
              <Text style={styles.cost}>{item.point_cost_snapshot} pts</Text>
            </View>
            <Field
              label="Optional comment"
              value={comments[item.id] ?? ""}
              onChangeText={(value) => setComments((current) => ({ ...current, [item.id]: value }))}
            />
            <View style={styles.actions}>
              <View style={styles.grow}><Button title="Approve" loading={action.isPending && action.variables?.key === `approve-redemption-${item.id}`} onPress={() => action.mutate({ key: `approve-redemption-${item.id}`, path: `/redemptions/${item.id}/approve`, body: { comment: comments[item.id] ?? "" } })} /></View>
              <View style={styles.grow}><Button title="Reject" variant="danger" loading={action.isPending && action.variables?.key === `reject-redemption-${item.id}`} onPress={() => action.mutate({ key: `reject-redemption-${item.id}`, path: `/redemptions/${item.id}/reject`, body: { comment: comments[item.id] ?? "" } })} /></View>
            </View>
          </Card>
        ))
      )}
    </Screen>
  );
}

function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card>
      <ErrorText message={message} />
      <Button title="Try again" variant="secondary" onPress={onRetry} />
    </Card>
  );
}

function queryErrorMessage(cause: Error | null, fallback: string) {
  return cause?.message || fallback;
}

const styles = StyleSheet.create({
  section: { color: colors.cocoa, fontSize: 20, fontWeight: "900", marginTop: spacing.sm },
  image: { width: "100%", height: 210, borderRadius: 12, backgroundColor: colors.border },
  titleRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  grow: { flex: 1 },
  title: { color: colors.cocoa, fontSize: 18, fontWeight: "900" },
  meta: { color: colors.muted, marginTop: 3 },
  body: { color: colors.cocoa, lineHeight: 20 },
  actions: { flexDirection: "row", gap: spacing.sm },
  cost: { color: colors.cocoa, fontWeight: "900", fontSize: 18 },
});
