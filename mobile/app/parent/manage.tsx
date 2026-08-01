import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import { File } from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import { useRef, useState } from "react";
import { Alert, Image, Modal, Pressable, ScrollView, Share, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { rewardImageUrl } from "@/api";
import { Button, Card, Empty, ErrorText, FeedbackBanner, Field, Header, IconButton, Pill, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";
import type { Child, Chore, HouseholdInvite, HouseholdMember, Reward, Role } from "@/types";

type Section = "CHILDREN" | "CHORES" | "REWARDS";

export default function Manage() {
  const { api, accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [section, setSection] = useState<Section>("CHILDREN");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [memberRole, setMemberRole] = useState<Role>("CHILD");
  const [generatedInvite, setGeneratedInvite] = useState<HouseholdInvite | null>(null);
  const [copyFeedback, setCopyFeedback] = useState("");
  const [rewardImage, setRewardImage] = useState<{ uri: string; name: string } | null>(null);
  const [openDropdown, setOpenDropdown] = useState<"ASSIGNEE" | "SCHEDULE" | null>(null);
  const emptyForm = { mode: "REUSABLE", assigned: "", schedule: "NONE", weekdayMask: "0", reminders: "true" };
  const [form, setForm] = useState<Record<string, string>>(emptyForm);
  const children = useQuery({ queryKey: ["children"], queryFn: () => api<Child[]>("/household/children") });
  const members = useQuery({ queryKey: ["members"], queryFn: () => api<HouseholdMember[]>("/household/members") });
  const chores = useQuery({ queryKey: ["chores"], queryFn: () => api<Chore[]>("/chores") });
  const rewards = useQuery({ queryKey: ["rewards"], queryFn: () => api<Reward[]>("/rewards") });
  const mutate = useMutation({
    mutationFn: async ({ key, path, method = "POST", body, image }: { key: string; path: string; method?: string; body?: object; image?: { uri: string; name: string } | null }) => {
      const result = await api<{ id?: string }>(path, { method, body: body ? JSON.stringify(body) : undefined });
      if (key === "save-reward" && image) {
        const rewardId = result?.id ?? path.split("/").filter(Boolean).at(-1);
        if (!rewardId) throw new Error("Could not identify the reward for its image.");
        const upload = new FormData();
        upload.append("image", new File(image.uri), image.name);
        await api(`/rewards/${rewardId}/image`, { method: "POST", body: upload });
      }
      return result;
    },
    onSuccess: async (data: unknown, variables) => {
      const result = data as (HouseholdInvite & { join_pin_expires_at?: string }) | undefined;
      if (variables.key === "add-member" && result?.join_pin) {
        setGeneratedInvite(result);
        setError("");
        await queryClient.invalidateQueries({ queryKey: ["members"] });
        return;
      }
      if (result?.join_pin) {
        Alert.alert(
          variables.path.endsWith("/join-pin") ? "New one-time join PIN" : "Child profile created",
          `PIN: ${result.join_pin}\n\nIt expires in one hour and can only be used once.`,
        );
      }
      setError("");
      setForm(emptyForm);
      setRewardImage(null);
      setEditingId(null);
      await queryClient.invalidateQueries();
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "Could not save"),
  });
  const update = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const create = () => {
    if (section === "CHORES")
      mutate.mutate({
        key: "save-chore",
        path: editingId ? `/chores/${editingId}` : "/chores",
        method: editingId ? "PATCH" : "POST",
        body: {
          title: form.title ?? "",
          description: form.description ?? "",
          suggested_points: Number(form.points ?? 0),
          mode: form.mode ?? "REUSABLE",
          assigned_to_user_id: form.assigned || null,
          schedule_type: form.schedule ?? "NONE",
          start_date: form.schedule === "NONE" ? null : form.startDate || null,
          due_local_time: form.schedule === "NONE" ? null : form.dueTime || null,
          weekday_mask: Number(form.weekdayMask ?? 0),
          reminders_enabled: form.reminders !== "false",
        },
      });
    if (section === "REWARDS")
      mutate.mutate({
        key: "save-reward",
        path: editingId ? `/rewards/${editingId}` : "/rewards",
        method: editingId ? "PATCH" : "POST",
        body: { name: form.name ?? "", description: form.description ?? "", point_cost: Number(form.cost ?? 0) },
        image: rewardImage,
      });
  };

  const beginChoreEdit = (chore: Chore) => {
    setEditingId(chore.id);
    setForm({
      ...emptyForm,
      title: chore.title,
      description: chore.description,
      points: String(chore.suggested_points),
      mode: chore.mode,
      assigned: chore.assigned_to_user_id ?? "",
      schedule: chore.schedule_type ?? "NONE",
      startDate: chore.start_date ?? "",
      dueTime: chore.due_local_time ?? "",
      weekdayMask: String(chore.weekday_mask ?? 0),
      reminders: chore.reminders_enabled ? "true" : "false",
    });
  };
  const beginRewardEdit = (reward: Reward) => {
    setEditingId(reward.id);
    setRewardImage(null);
    setForm({ ...emptyForm, name: reward.name, description: reward.description, cost: String(reward.point_cost) });
  };

  const pickRewardImage = async () => {
    setError("");
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setError("Allow photo access to choose a reward image.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.75 });
    if (result.canceled) return;
    const asset = result.assets[0];
    setRewardImage({ uri: asset.uri, name: asset.fileName ?? `reward-${Date.now()}.jpg` });
  };
  const confirmChildDelete = (child: { id: string; display_name: string }) =>
    Alert.alert(`Delete ${child.display_name}?`, `Are you sure you want to delete ${child.display_name}? You can undo this for 30 days.`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete user",
        style: "destructive",
        onPress: () => mutate.mutate({
          key: `delete-member-${child.id}`,
          path: `/household/children/${child.id}/deletion`,
        }),
      },
    ]);

  const confirmDeactivate = (kind: "chore" | "reward", id: string, name: string) =>
    Alert.alert(`Remove ${name}?`, `This ${kind} will no longer be available.`, [
      { text: "Cancel", style: "cancel" },
      { text: "Remove", style: "destructive", onPress: () => mutate.mutate({ key: `deactivate-${kind}-${id}`, path: `/${kind}s/${id}`, method: "DELETE" }) },
    ]);

  const addMember = () => mutate.mutate({
    key: "add-member",
    path: "/household/invites",
    body: { role: memberRole },
  });

  const inviteMessage = generatedInvite
    ? `You're invited to join ${generatedInvite.family_name} in Sibling Rewards as a ${generatedInvite.role.toLowerCase()}.\n\nFamily code: ${generatedInvite.family_code}\nOne-time code: ${generatedInvite.join_pin}\n\nSign in or create your account, choose Join a household, and enter both codes. This invitation expires in one hour and can only be used once.`
    : "";

  const shareInvite = async () => {
    if (!generatedInvite) return;
    await Share.share({ title: `Join ${generatedInvite.family_name}`, message: inviteMessage });
  };

  const copyInvite = async () => {
    if (!generatedInvite) return;
    await Clipboard.setStringAsync(inviteMessage);
    setCopyFeedback("Invite details copied and ready to paste.");
  };

  return (
    <Screen scrollEnabled={openDropdown === null}>
      <Header eyebrow="Household setup" title="Manage" />
      <View style={styles.segment}>
        {(["CHILDREN", "CHORES", "REWARDS"] as Section[]).map((item) => (
          <Pressable key={item} onPress={() => { setSection(item); setEditingId(null); setRewardImage(null); setOpenDropdown(null); setForm(emptyForm); }} style={[styles.segmentItem, section === item && styles.segmentActive]}>
            <Text style={[styles.segmentText, section === item && styles.segmentTextActive]}>{item.toLowerCase()}</Text>
          </Pressable>
        ))}
      </View>
      <ErrorText message={error} />
      {section === "CHILDREN" ? (
        <Card style={styles.addMemberCard}>
          <View style={styles.grow}>
            <Text style={styles.formTitle}>Household members</Text>
            <Text style={styles.body}>Invite a parent or child with a one-hour, single-use code.</Text>
          </View>
          <Button title="Add member" icon="person-add-outline" onPress={() => { setError(""); setCopyFeedback(""); setMemberRole("CHILD"); setGeneratedInvite(null); setMemberModalOpen(true); }} />
        </Card>
      ) : <Card>
        <Text style={styles.formTitle}>{editingId ? "Edit" : "Add"} {section === "CHORES" ? "a chore" : "a reward"}</Text>
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
            <Dropdown label="Assign to" value={form.assigned || ""} open={openDropdown === "ASSIGNEE"} onToggle={() => setOpenDropdown((current) => current === "ASSIGNEE" ? null : "ASSIGNEE")} onChange={(value) => { update("assigned", value); setOpenDropdown(null); }} options={[{ value: "", label: "Everyone" }, ...(children.data?.filter((child) => child.is_active).map((child) => ({ value: child.id, label: child.display_name })) ?? [])]} />
            <Dropdown label="Schedule" value={form.schedule ?? "NONE"} open={openDropdown === "SCHEDULE"} onToggle={() => setOpenDropdown((current) => current === "SCHEDULE" ? null : "SCHEDULE")} onChange={(value) => { update("schedule", value); setOpenDropdown(null); }} options={[{ value: "NONE", label: "None" }, { value: "WEEKDAYS", label: "Weekdays" }, { value: "WEEKENDS", label: "Weekends" }, { value: "WEEKLY", label: "Weekly" }, { value: "DAILY", label: "Daily" }, { value: "MONTHLY", label: "Monthly" }]} />
            {form.schedule !== "NONE" ? (
              <>
                <Field label={form.schedule === "WEEKLY" ? "First date (sets weekday)" : form.schedule === "MONTHLY" ? "First date (sets day of month)" : "Start date (YYYY-MM-DD)"} value={form.startDate ?? ""} onChangeText={(value) => update("startDate", value)} placeholder="2026-08-01" />
                <Field label="Due time (24-hour HH:MM)" value={form.dueTime ?? ""} onChangeText={(value) => update("dueTime", value)} placeholder="18:00" />
                <Choice selected={form.reminders !== "false"} label="Reminders on" onPress={() => update("reminders", form.reminders === "false" ? "true" : "false")} />
              </>
            ) : null}
          </>
        ) : null}
        {section === "REWARDS" ? (
          <>
            <Field label="Reward name" value={form.name ?? ""} onChangeText={(value) => update("name", value)} />
            <Field label="Description" multiline value={form.description ?? ""} onChangeText={(value) => update("description", value)} />
            <Field label="Point cost" keyboardType="number-pad" value={form.cost ?? ""} onChangeText={(value) => update("cost", value)} />
            <Text style={styles.label}>Reward image (optional)</Text>
            <Pressable accessibilityRole="button" accessibilityLabel="Choose a reward image" onPress={pickRewardImage} style={({ pressed }) => [styles.rewardImagePicker, pressed && styles.pressed]}>
              {rewardImage ? <Image source={{ uri: rewardImage.uri }} style={styles.rewardImagePreview} /> : editingId && rewards.data?.find((reward) => reward.id === editingId)?.has_image ? <Image source={{ uri: rewardImageUrl(editingId), headers: { Authorization: `Bearer ${accessToken}` } }} style={styles.rewardImagePreview} /> : <><Ionicons name="images-outline" size={30} color={colors.peach} /><Text style={styles.meta}>Tap to choose an image</Text></>}
            </Pressable>
          </>
        ) : null}
        <Button title={editingId ? "Save changes" : "Add"} loading={mutate.isPending && mutate.variables?.key === (section === "CHORES" ? "save-chore" : "save-reward")} onPress={create} />
        {editingId ? <Button title="Cancel editing" variant="ghost" onPress={() => { setEditingId(null); setRewardImage(null); setForm(emptyForm); }} /> : null}
      </Card>}

      <Text style={styles.sectionTitle}>{section === "CHILDREN" ? "Current members" : `Current ${section.toLowerCase()}`}</Text>
      {section === "CHILDREN" ? (
        members.data?.length ? members.data.map((member) => (
          <Card key={member.id}>
            <View style={styles.row}>
              <View style={styles.grow}><Text style={styles.itemTitle}>{member.display_name}</Text><Text style={styles.meta}>{member.role === "PARENT" ? "Parent" : "Child"} · {member.account_type === "ACCOUNT" ? "Account connected" : "Legacy profile"}</Text></View>
              {member.role === "CHILD" && member.account_type === "ACCOUNT" && member.is_active ? <IconButton compact compactSize="medium" icon="trash-outline" label={`Delete ${member.display_name}`} variant="danger" loading={mutate.isPending && mutate.variables?.key === `delete-member-${member.id}`} onPress={() => confirmChildDelete(member)} /> : null}
            </View>
            {member.role === "CHILD" && member.deletion_scheduled_for ? (
              <Button title="Undo deletion" variant="secondary" loading={mutate.isPending && mutate.variables?.key === `undo-delete-${member.id}`} onPress={() => mutate.mutate({ key: `undo-delete-${member.id}`, path: `/household/children/${member.id}/deletion/cancel` })} />
            ) : null}
          </Card>
        )) : <Empty title="No household members" message="Generate an invitation to add a parent or child." />
      ) : null}
      {section === "CHORES" ? (
        chores.data?.length ? chores.data.map((chore) => (
          <Card key={chore.id}>
            <View style={styles.row}>
              <View style={styles.grow}><Text style={styles.itemTitle}>{chore.title}</Text><Text style={styles.meta}>{chore.assigned_to_name ?? "Everyone"} · {chore.suggested_points} pts · {chore.schedule_type === "NONE" ? "No schedule" : chore.schedule_type.toLowerCase()}</Text>{chore.description ? <Text numberOfLines={2} style={styles.body}>{chore.description}</Text> : null}{chore.next_due_at ? <Text style={styles.meta}>{chore.next_occurrence_status === "OVERDUE" ? "Overdue" : "Next due"}: {new Date(chore.next_due_at).toLocaleString()}</Text> : null}</View>
              {chore.state === "ACTIVE" ? <View style={styles.compactActions}><IconButton compact icon="pencil-outline" label={`Edit ${chore.title}`} onPress={() => beginChoreEdit(chore)} /><IconButton compact icon="trash-outline" label={`Remove ${chore.title}`} variant="danger" loading={mutate.isPending && mutate.variables?.key === `deactivate-chore-${chore.id}`} onPress={() => confirmDeactivate("chore", chore.id, chore.title)} /></View> : <Pill label={chore.state} tone="neutral" />}
            </View>
          </Card>
        )) : <Empty title="No chores yet" message="Create a reusable activity or one-time household task." />
      ) : null}
      {section === "REWARDS" ? (
        rewards.data?.length ? rewards.data.map((reward) => (
          <Card key={reward.id}>
            <View style={styles.row}>
              {reward.has_image ? <Image source={{ uri: rewardImageUrl(reward.id), headers: { Authorization: `Bearer ${accessToken}` } }} style={styles.rewardThumb} /> : <View style={styles.rewardThumbPlaceholder}><Ionicons name="gift-outline" size={22} color={colors.cocoa} /></View>}
              <View style={styles.grow}><Text style={styles.itemTitle}>{reward.name}</Text><Text style={styles.meta}>{reward.point_cost} points</Text>{reward.description ? <Text numberOfLines={2} style={styles.body}>{reward.description}</Text> : null}</View>
              {reward.is_active ? <View style={styles.compactActions}><IconButton compact icon="pencil-outline" label={`Edit ${reward.name}`} onPress={() => beginRewardEdit(reward)} /><IconButton compact icon="trash-outline" label={`Remove ${reward.name}`} variant="danger" loading={mutate.isPending && mutate.variables?.key === `deactivate-reward-${reward.id}`} onPress={() => confirmDeactivate("reward", reward.id, reward.name)} /></View> : <Pill label="Inactive" tone="neutral" />}
            </View>
          </Card>
        )) : <Empty title="No rewards yet" message="Add something worth saving points for." />
      ) : null}
      <Modal visible={memberModalOpen} transparent animationType="fade" onRequestClose={() => setMemberModalOpen(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setMemberModalOpen(false)}>
          <Pressable style={styles.modalSurface} onPress={(event) => event.stopPropagation()}>
          <Card style={styles.modalCard}>
            <View style={styles.modalHeading}>
              <View style={styles.grow}><Text style={styles.formTitle}>{generatedInvite ? "Invite ready" : "Add member"}</Text><Text style={styles.body}>{generatedInvite ? `Share these details with the new ${generatedInvite.role.toLowerCase()}.` : "Choose the role this person will have in your household."}</Text></View>
            </View>
            {generatedInvite ? (
              <>
                <View style={styles.inviteRole}><Pill label={generatedInvite.role} tone={generatedInvite.role === "PARENT" ? "info" : "success"} /><Text style={styles.meta}>Expires in one hour · Single use</Text></View>
                <InviteCode label="Family code" value={generatedInvite.family_code} onCopy={async () => { await Clipboard.setStringAsync(generatedInvite.family_code); setCopyFeedback("Family code copied."); }} />
                <InviteCode label="One-time code" value={generatedInvite.join_pin} onCopy={async () => { await Clipboard.setStringAsync(generatedInvite.join_pin); setCopyFeedback("One-time code copied."); }} />
                <FeedbackBanner message={copyFeedback} tone="info" />
                <Button title="Share invitation" icon="share-social-outline" onPress={shareInvite} />
                <Button title="Copy all details" variant="secondary" icon="copy-outline" onPress={copyInvite} />
                <Button title="Done" variant="ghost" onPress={() => setMemberModalOpen(false)} />
              </>
            ) : (
              <>
                <Text style={styles.label}>Invite as</Text>
                <View style={styles.choices}>
                  <Choice selected={memberRole === "CHILD"} label="Child" onPress={() => setMemberRole("CHILD")} />
                  <Choice selected={memberRole === "PARENT"} label="Parent" onPress={() => setMemberRole("PARENT")} />
                </View>
                {memberRole === "PARENT" ? <Text style={styles.warning}>Parents can manage members, chores, rewards, approvals, and household settings.</Text> : null}
                <Text style={styles.meta}>Their account name will be used after they join.</Text>
                <ErrorText message={error} />
                <Button title="Generate invitation" loading={mutate.isPending && mutate.variables?.key === "add-member"} onPress={addMember} />
                <Button title="Cancel" variant="ghost" disabled={mutate.isPending} onPress={() => setMemberModalOpen(false)} />
              </>
            )}
          </Card>
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  );
}

function InviteCode({ label, value, onCopy }: { label: string; value: string; onCopy: () => Promise<unknown> }) {
  return <View style={styles.codeCard}><View style={styles.grow}><Text style={styles.codeLabel}>{label}</Text><Text selectable style={styles.codeValue}>{value}</Text></View><Pressable accessibilityRole="button" accessibilityLabel={`Copy ${label}`} onPress={onCopy} style={styles.copyButton}><Ionicons name="copy-outline" size={20} color={colors.peach} /></Pressable></View>;
}

function Dropdown({ label, value, options, open, onToggle, onChange }: { label: string; value: string; options: { value: string; label: string }[]; open: boolean; onToggle: () => void; onChange: (value: string) => void }) {
  const selected = options.find((option) => option.value === value)?.label ?? "Select";
  const buttonRef = useRef<View>(null);
  const { height: windowHeight } = useWindowDimensions();
  const [anchor, setAnchor] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const menuHeight = Math.min(options.length * 48 + 2, 220);
  const menuTop = Math.max(spacing.sm, Math.min(anchor.y + anchor.height + 4, windowHeight - 110 - menuHeight));

  const toggle = () => {
    if (open) {
      onToggle();
      return;
    }
    buttonRef.current?.measureInWindow((x, y, width, height) => {
      setAnchor({ x, y, width, height });
      onToggle();
    });
  };

  return (
    <View style={[styles.dropdownWrap, open && styles.dropdownWrapOpen]}>
      <Text style={styles.label}>{label}</Text>
      <View ref={buttonRef} collapsable={false}>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={`${label}: ${selected}`} onPress={toggle} style={({ pressed }) => [styles.dropdownButton, open && styles.dropdownButtonOpen, pressed && styles.pressed]}>
          <Text style={styles.dropdownValue}>{selected}</Text>
          <Ionicons name={open ? "chevron-up" : "chevron-down"} size={19} color={colors.peach} />
        </Pressable>
      </View>
      <Modal animationType="none" onRequestClose={onToggle} statusBarTranslucent transparent visible={open}>
        <View style={styles.dropdownModal}>
          <Pressable accessibilityLabel={`Close ${label} options`} onPress={onToggle} style={StyleSheet.absoluteFill} />
          <ScrollView
            style={[styles.dropdownMenu, { top: menuTop, left: anchor.x, width: anchor.width, height: menuHeight }]}
            contentContainerStyle={styles.dropdownMenuContent}
            keyboardShouldPersistTaps="handled"
            overScrollMode="never"
            showsVerticalScrollIndicator
          >
            {options.map((option, index) => (
              <Pressable key={`${option.value}-${option.label}`} accessibilityRole="button" onPress={() => onChange(option.value)} style={({ pressed }) => [styles.dropdownOption, index > 0 && styles.dropdownRule, option.value === value && styles.dropdownOptionSelected, pressed && styles.pressed]}>
                <Text style={[styles.dropdownOptionText, option.value === value && styles.dropdownOptionTextSelected]}>{option.label}</Text>
                {option.value === value ? <Ionicons name="checkmark" size={19} color={colors.cocoa} /> : null}
              </Pressable>
            ))}
          </ScrollView>
        </View>
      </Modal>
    </View>
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
  dropdownWrap: { gap: spacing.xs, position: "relative", zIndex: 1 },
  dropdownWrapOpen: { zIndex: 50, elevation: 12 },
  dropdownButton: { minHeight: 52, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.white, paddingHorizontal: spacing.md, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  dropdownButtonOpen: { borderColor: colors.peach },
  dropdownValue: { color: colors.cocoa, fontWeight: "800", fontSize: 16 },
  dropdownModal: { flex: 1 },
  dropdownMenu: { position: "absolute", borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.cream, shadowColor: colors.cocoa, shadowOpacity: 0.18, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 12 },
  dropdownMenuContent: { overflow: "hidden", borderRadius: radius.sm },
  dropdownOption: { minHeight: 48, paddingHorizontal: spacing.md, flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: colors.cream },
  dropdownOptionSelected: { backgroundColor: colors.sun },
  dropdownRule: { borderTopWidth: 1, borderTopColor: colors.border },
  dropdownOptionText: { color: colors.muted, fontWeight: "700" },
  dropdownOptionTextSelected: { color: colors.cocoa, fontWeight: "900" },
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
  addMemberCard: { gap: spacing.md },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(64, 45, 36, 0.38)", justifyContent: "center", padding: spacing.lg },
  modalSurface: { width: "100%" },
  modalCard: { padding: spacing.lg, gap: spacing.md },
  modalHeading: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  compactActions: { alignItems: "flex-end", gap: spacing.sm },
  rewardImagePicker: { height: 150, borderRadius: radius.md, borderWidth: 2, borderStyle: "dashed", borderColor: colors.border, backgroundColor: colors.white, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  rewardImagePreview: { width: "100%", height: "100%" },
  rewardThumb: { width: 60, height: 60, borderRadius: radius.sm, backgroundColor: colors.border },
  rewardThumbPlaceholder: { width: 60, height: 60, borderRadius: radius.sm, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  inviteRole: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  warning: { color: colors.danger, lineHeight: 20, fontWeight: "700" },
  codeCard: { minHeight: 74, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.white, flexDirection: "row", alignItems: "center", gap: spacing.md },
  codeLabel: { color: colors.muted, fontSize: 12, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.5 },
  codeValue: { color: colors.cocoa, fontSize: 24, fontWeight: "900", letterSpacing: 3, marginTop: 3 },
  copyButton: { width: 44, height: 44, borderRadius: 14, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  pressed: { opacity: 0.7 },
});
