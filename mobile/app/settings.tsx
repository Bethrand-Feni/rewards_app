import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, StyleSheet, Text } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, ErrorText, FeedbackBanner, Field, Header, IconButton, Screen } from "@/components";
import { enablePushNotifications, pushNotificationsSupported } from "@/notifications";
import { colors, spacing } from "@/theme";

export default function Settings() {
  const auth = useAuth();
  const [familyName, setFamilyName] = useState("");
  const [password, setPassword] = useState("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const canEnablePush = pushNotificationsSupported();

  useEffect(() => {
    auth.refreshUser().catch(() => undefined);
  }, [auth.refreshUser]);

  const enablePush = async () => {
    setPendingAction("notifications");
    setError("");
    try {
      await enablePushNotifications(auth.api);
      setMessage("Notifications are enabled on this device.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not enable notifications");
    } finally {
      setPendingAction(null);
    }
  };

  const scheduleDeletion = async (withGoogle: boolean) => {
    setPendingAction(withGoogle ? "delete-google" : "delete-password");
    setError("");
    try {
      const proof = withGoogle ? await auth.googleProof() : { password };
      const result = await auth.api<{ execute_after: string }>("/account/deletion", {
        method: "POST",
        body: JSON.stringify({ family_name: familyName, ...proof }),
      });
      await auth.refreshUser();
      setMessage(`Deletion is scheduled for ${new Date(result.execute_after).toLocaleDateString()}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not schedule deletion");
    } finally {
      setPendingAction(null);
    }
  };

  const confirmDeletion = (withGoogle: boolean) => {
    Alert.alert(
      "Schedule household deletion?",
      "The household and all child data will be removed after 30 days. You can cancel before then.",
      [
        { text: "Keep household", style: "cancel" },
        { text: "Schedule deletion", style: "destructive", onPress: () => void scheduleDeletion(withGoogle) },
      ],
    );
  };

  const cancelDeletion = async () => {
    setPendingAction("cancel-deletion");
    setError("");
    try {
      await auth.api("/account/deletion/cancel", { method: "POST" });
      await auth.refreshUser();
      setMessage("Household deletion was cancelled.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not cancel deletion");
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <Screen>
      <Header eyebrow="Account" title="Settings" action={<IconButton icon="arrow-back" label="Go back" onPress={() => router.back()} />} />
      <ErrorText message={error} />
      <FeedbackBanner message={message} />
      <Card>
        <Text style={styles.title}>Notifications</Text>
        <Text style={styles.body}>
          {canEnablePush
            ? "Get reminders, review results, point updates, and reward decisions on this device."
            : "Push notifications are unavailable in Expo Go. Install a development build to test them."}
        </Text>
        <Button
          title={canEnablePush ? "Enable notifications" : "Development build required"}
          onPress={enablePush}
          loading={pendingAction === "notifications"}
          disabled={!canEnablePush}
        />
      </Card>
      {auth.user?.role === "PARENT" ? (
        <Card>
          <Text style={styles.title}>Delete account and household</Text>
          {auth.user.deletion_scheduled_for ? (
            <>
              <Text style={styles.warning}>
                Scheduled for {new Date(auth.user.deletion_scheduled_for).toLocaleDateString()}.
              </Text>
              <Button title="Cancel deletion" variant="secondary" onPress={cancelDeletion} loading={pendingAction === "cancel-deletion"} />
            </>
          ) : (
            <>
              <Text style={styles.body}>
                This includes your parent account, children, photos, chores, points, and rewards. Recovery remains available for 30 days.
              </Text>
              <Field label="Type the household name" value={familyName} onChangeText={setFamilyName} />
              <Field label="Confirm with password" secureTextEntry value={password} onChangeText={setPassword} />
              <Button
                title="Schedule deletion with password"
                variant="danger"
                disabled={!familyName || !password}
                onPress={() => confirmDeletion(false)}
                loading={pendingAction === "delete-password"}
              />
              <Button
                title="Schedule deletion with Google"
                variant="secondary"
                disabled={!familyName}
                onPress={() => confirmDeletion(true)}
                loading={pendingAction === "delete-google"}
              />
            </>
          )}
        </Card>
      ) : null}
      <Button title="Log out" variant="secondary" onPress={auth.logout} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.cocoa, fontSize: 18, fontWeight: "900" },
  body: { color: colors.muted, lineHeight: 20 },
  warning: { color: colors.danger, fontWeight: "800", lineHeight: 20 },
});
