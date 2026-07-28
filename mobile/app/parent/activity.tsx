import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, Empty, ErrorText, Field, Header, Pill, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Child, PointTransaction } from "@/types";

export default function ParentActivity() {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const children = useQuery({ queryKey: ["children"], queryFn: () => api<Child[]>("/household/children") });
  const history = useQuery({
    queryKey: ["points", "history", selected],
    queryFn: () => api<PointTransaction[]>(`/points/history?child_user_id=${selected}`),
    enabled: Boolean(selected),
  });
  const balance = useQuery({
    queryKey: ["points", "balance", selected],
    queryFn: () => api<{ balance: number }>(`/points/balance?child_user_id=${selected}`),
    enabled: Boolean(selected),
  });
  const adjust = useMutation({
    mutationFn: () => api("/points/adjustments", { method: "POST", body: JSON.stringify({ child_user_id: selected, amount: Number(amount), reason }) }),
    onSuccess: async () => { setAmount(""); setReason(""); setError(""); await queryClient.invalidateQueries({ queryKey: ["points"] }); },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "Adjustment failed"),
  });

  return (
    <Screen>
      <Header eyebrow="Points ledger" title="Activity" />
      <Text style={styles.label}>Choose a child</Text>
      <View style={styles.wrap}>
        {children.data?.filter((child) => child.is_active).map((child) => (
          <Pressable key={child.id} onPress={() => setSelected(child.id)} style={[styles.choice, selected === child.id && styles.selected]}>
            <Text style={[styles.choiceText, selected === child.id && styles.selectedText]}>{child.display_name}</Text>
          </Pressable>
        ))}
      </View>
      {!selected ? (
        <Empty title="Select a profile" message="Choose a child to see their balance and ledger." />
      ) : (
        <>
          <Card style={styles.balanceCard}>
            <Text style={styles.balanceLabel}>Current balance</Text>
            <Text style={styles.balance}>{balance.data?.balance ?? 0} pts</Text>
          </Card>
          <Card>
            <Text style={styles.title}>Manual adjustment</Text>
            <Text style={styles.help}>Use a negative number to deduct points. A reason is always recorded.</Text>
            <Field label="Amount" keyboardType="numbers-and-punctuation" value={amount} onChangeText={setAmount} />
            <Field label="Reason" value={reason} onChangeText={setReason} />
            <ErrorText message={error} />
            <Button title="Record adjustment" loading={adjust.isPending} disabled={!amount || reason.trim().length < 3} onPress={() => adjust.mutate()} />
          </Card>
          <Text style={styles.title}>Recent transactions</Text>
          {!history.data?.length ? <Empty title="No activity yet" message="Approved chores and rewards will build this ledger." /> : history.data.map((item) => (
            <Card key={item.id} style={styles.transaction}>
              <View style={styles.grow}><Text style={styles.transactionReason}>{item.reason}</Text><Text style={styles.date}>{new Date(item.created_at).toLocaleString()}</Text></View>
              <View style={styles.amount}><Text style={[styles.amountText, item.amount < 0 && styles.negative]}>{item.amount > 0 ? "+" : ""}{item.amount}</Text><Pill label={item.transaction_type} tone={item.amount > 0 ? "success" : "info"} /></View>
            </Card>
          ))}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  label: { color: colors.cocoa, fontWeight: "900" },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  choice: { paddingHorizontal: 16, minHeight: 42, justifyContent: "center", borderRadius: radius.pill, backgroundColor: colors.cream, borderWidth: 1, borderColor: colors.border },
  selected: { backgroundColor: colors.sun, borderColor: colors.sun },
  choiceText: { color: colors.muted, fontWeight: "800" },
  selectedText: { color: colors.cocoa },
  balanceCard: { backgroundColor: colors.sun, alignItems: "center", paddingVertical: spacing.lg },
  balanceLabel: { color: colors.cocoa, fontWeight: "800" },
  balance: { color: colors.cocoa, fontSize: 34, fontWeight: "900" },
  title: { color: colors.cocoa, fontSize: 19, fontWeight: "900" },
  help: { color: colors.muted, lineHeight: 19 },
  transaction: { flexDirection: "row", alignItems: "center" },
  grow: { flex: 1 },
  transactionReason: { color: colors.cocoa, fontWeight: "800" },
  date: { color: colors.muted, fontSize: 12, marginTop: 4 },
  amount: { alignItems: "flex-end", gap: 5 },
  amountText: { color: colors.success, fontWeight: "900", fontSize: 20 },
  negative: { color: colors.danger },
});

