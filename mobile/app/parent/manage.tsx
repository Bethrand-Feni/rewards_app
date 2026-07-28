import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, Empty, ErrorText, Field, Header, Pill, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Child, Chore, Reward } from "@/types";

type Section = "CHILDREN" | "CHORES" | "REWARDS";

export default function Manage() {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const [section, setSection] = useState<Section>("CHILDREN");
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string>>({ mode: "REUSABLE", assigned: "" });
  const children = useQuery({ queryKey: ["children"], queryFn: () => api<Child[]>("/household/children") });
  const chores = useQuery({ queryKey: ["chores"], queryFn: () => api<Chore[]>("/chores") });
  const rewards = useQuery({ queryKey: ["rewards"], queryFn: () => api<Reward[]>("/rewards") });
  const mutate = useMutation({
    mutationFn: ({ path, method = "POST", body }: { path: string; method?: string; body?: object }) =>
      api(path, { method, body: body ? JSON.stringify(body) : undefined }),
    onSuccess: async () => {
      setError("");
      setForm({ mode: "REUSABLE", assigned: "" });
      await queryClient.invalidateQueries();
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "Could not save"),
  });
  const update = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const create = () => {
    if (section === "CHILDREN")
      mutate.mutate({
        path: "/household/children",
        body: { display_name: form.name ?? "", username: form.username ?? "", pin: form.pin ?? "" },
      });
    if (section === "CHORES")
      mutate.mutate({
        path: "/chores",
        body: {
          title: form.title ?? "",
          description: form.description ?? "",
          suggested_points: Number(form.points ?? 0),
          mode: form.mode ?? "REUSABLE",
          assigned_to_user_id: form.assigned || null,
        },
      });
    if (section === "REWARDS")
      mutate.mutate({
        path: "/rewards",
        body: { name: form.name ?? "", description: form.description ?? "", point_cost: Number(form.cost ?? 0) },
      });
  };

  return (
    <Screen>
      <Header eyebrow="Household setup" title="Manage" />
      <View style={styles.segment}>
        {(["CHILDREN", "CHORES", "REWARDS"] as Section[]).map((item) => (
          <Pressable key={item} onPress={() => { setSection(item); setForm({ mode: "REUSABLE", assigned: "" }); }} style={[styles.segmentItem, section === item && styles.segmentActive]}>
            <Text style={[styles.segmentText, section === item && styles.segmentTextActive]}>{item.toLowerCase()}</Text>
          </Pressable>
        ))}
      </View>
      <ErrorText message={error} />
      <Card>
        <Text style={styles.formTitle}>Add {section === "CHILDREN" ? "a child profile" : section === "CHORES" ? "a chore" : "a reward"}</Text>
        {section === "CHILDREN" ? (
          <>
            <Field label="Display name" value={form.name ?? ""} onChangeText={(value) => update("name", value)} />
            <Field label="Username" autoCapitalize="none" value={form.username ?? ""} onChangeText={(value) => update("username", value)} />
            <Field label="4–6 digit PIN" keyboardType="number-pad" secureTextEntry maxLength={6} value={form.pin ?? ""} onChangeText={(value) => update("pin", value)} />
          </>
        ) : null}
        {section === "CHORES" ? (
          <>
            <Field label="Chore title" value={form.title ?? ""} onChangeText={(value) => update("title", value)} />
            <Field label="Description" multiline value={form.description ?? ""} onChangeText={(value) => update("description", value)} />
            <Field label="Suggested points" keyboardType="number-pad" value={form.points ?? ""} onChangeText={(value) => update("points", value)} />
            <Text style={styles.label}>Chore type</Text>
            <View style={styles.choices}>
              <Choice selected={form.mode === "REUSABLE"} label="Reusable" onPress={() => update("mode", "REUSABLE")} />
              <Choice selected={form.mode === "ONE_TIME"} label="One-time" onPress={() => update("mode", "ONE_TIME")} />
            </View>
            <Text style={styles.label}>Assign to</Text>
            <View style={styles.wrap}>
              <Choice selected={!form.assigned} label="Everyone" onPress={() => update("assigned", "")} />
              {children.data?.filter((child) => child.is_active).map((child) => (
                <Choice key={child.id} selected={form.assigned === child.id} label={child.display_name} onPress={() => update("assigned", child.id)} />
              ))}
            </View>
          </>
        ) : null}
        {section === "REWARDS" ? (
          <>
            <Field label="Reward name" value={form.name ?? ""} onChangeText={(value) => update("name", value)} />
            <Field label="Description" multiline value={form.description ?? ""} onChangeText={(value) => update("description", value)} />
            <Field label="Point cost" keyboardType="number-pad" value={form.cost ?? ""} onChangeText={(value) => update("cost", value)} />
          </>
        ) : null}
        <Button title="Add" loading={mutate.isPending} onPress={create} />
      </Card>

      <Text style={styles.sectionTitle}>Current {section.toLowerCase()}</Text>
      {section === "CHILDREN" ? (
        children.data?.length ? children.data.map((child) => (
          <Card key={child.id}>
            <View style={styles.row}>
              <View style={styles.grow}><Text style={styles.itemTitle}>{child.display_name}</Text><Text style={styles.meta}>@{child.username}</Text></View>
              <Pill label={child.is_active ? "Active" : "Inactive"} tone={child.is_active ? "success" : "neutral"} />
            </View>
            {child.is_active ? <Button title="Deactivate" variant="danger" onPress={() => mutate.mutate({ path: `/household/children/${child.id}/deactivate`, method: "PATCH" })} /> : null}
          </Card>
        )) : <Empty title="No child profiles" message="Create a profile to begin the household loop." />
      ) : null}
      {section === "CHORES" ? (
        chores.data?.length ? chores.data.map((chore) => (
          <Card key={chore.id}>
            <View style={styles.row}><View style={styles.grow}><Text style={styles.itemTitle}>{chore.title}</Text><Text style={styles.meta}>{chore.assigned_to_name ?? "Everyone"} · {chore.suggested_points} pts</Text></View><Pill label={chore.mode} tone="info" /></View>
            <Text style={styles.body}>{chore.description || "No description"}</Text>
            <Button title="Deactivate" variant="danger" onPress={() => mutate.mutate({ path: `/chores/${chore.id}`, method: "DELETE" })} />
          </Card>
        )) : <Empty title="No chores yet" message="Create a reusable activity or one-time household task." />
      ) : null}
      {section === "REWARDS" ? (
        rewards.data?.length ? rewards.data.map((reward) => (
          <Card key={reward.id}>
            <View style={styles.row}><View style={styles.grow}><Text style={styles.itemTitle}>{reward.name}</Text><Text style={styles.meta}>{reward.point_cost} points</Text></View><Pill label={reward.is_active ? "Active" : "Inactive"} tone={reward.is_active ? "success" : "neutral"} /></View>
            <Text style={styles.body}>{reward.description || "No description"}</Text>
            {reward.is_active ? <Button title="Deactivate" variant="danger" onPress={() => mutate.mutate({ path: `/rewards/${reward.id}`, method: "DELETE" })} /> : null}
          </Card>
        )) : <Empty title="No rewards yet" message="Add something worth saving points for." />
      ) : null}
    </Screen>
  );
}

function Choice({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return <Pressable onPress={onPress} style={[styles.choice, selected && styles.choiceSelected]}><Text style={[styles.choiceText, selected && styles.choiceTextSelected]}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  segment: { flexDirection: "row", padding: 4, borderRadius: radius.sm, backgroundColor: "#EEE4D0" },
  segmentItem: { flex: 1, minHeight: 42, borderRadius: 8, alignItems: "center", justifyContent: "center" },
  segmentActive: { backgroundColor: colors.cream },
  segmentText: { color: colors.muted, fontWeight: "800", textTransform: "capitalize" },
  segmentTextActive: { color: colors.cocoa },
  formTitle: { color: colors.cocoa, fontWeight: "900", fontSize: 19 },
  label: { color: colors.cocoa, fontWeight: "800", fontSize: 13 },
  choices: { flexDirection: "row", gap: spacing.sm },
  wrap: { flexDirection: "row", gap: spacing.sm, flexWrap: "wrap" },
  choice: { minHeight: 40, justifyContent: "center", paddingHorizontal: 14, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.white },
  choiceSelected: { backgroundColor: colors.sun, borderColor: colors.sun },
  choiceText: { color: colors.muted, fontWeight: "800" },
  choiceTextSelected: { color: colors.cocoa },
  sectionTitle: { color: colors.cocoa, fontWeight: "900", fontSize: 20, textTransform: "capitalize" },
  row: { flexDirection: "row", gap: spacing.md, alignItems: "center" },
  grow: { flex: 1 },
  itemTitle: { color: colors.cocoa, fontWeight: "900", fontSize: 17 },
  meta: { color: colors.muted, marginTop: 3 },
  body: { color: colors.cocoa, lineHeight: 20 },
});

