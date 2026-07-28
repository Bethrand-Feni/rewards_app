import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, ErrorText, Field, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";

type Mode = "CHOOSER" | "PARENT_LOGIN" | "PARENT_REGISTER" | "CHILD_LOGIN";

export default function AuthScreen() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>("CHOOSER");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});

  const update = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const title =
    mode === "CHOOSER"
      ? "Good things deserve a little celebration."
      : mode === "PARENT_REGISTER"
        ? "Create your household"
        : mode === "PARENT_LOGIN"
          ? "Parent sign in"
          : "Child sign in";

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (mode === "PARENT_LOGIN") await auth.parentLogin(form.email ?? "", form.password ?? "");
      if (mode === "PARENT_REGISTER") {
        if ((form.password ?? "").length < 10) {
          throw new Error("Password must be at least 10 characters.");
        }
        await auth.parentRegister({
          family_name: form.familyName ?? "",
          display_name: form.displayName ?? "",
          email: form.email ?? "",
          password: form.password ?? "",
        });
      }
      if (mode === "CHILD_LOGIN")
        await auth.childLogin(form.familyCode ?? "", form.username ?? "", form.pin ?? "");
      router.replace("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen contentStyle={styles.screen}>
      <View style={styles.brand}>
        <View style={styles.mark}>
          <Ionicons name="star" size={30} color={colors.cocoa} />
        </View>
        <Text style={styles.brandName}>Sibling Rewards</Text>
        <Text style={styles.tagline}>{title}</Text>
      </View>

      <Card style={styles.panel}>
        {mode === "CHOOSER" ? (
          <>
            <RoleCard
              icon="shield-checkmark-outline"
              title="I'm the parent"
              text="Manage chores, reviews, points and rewards."
              onPress={() => setMode("PARENT_LOGIN")}
            />
            <RoleCard
              icon="sparkles-outline"
              title="I'm completing chores"
              text="Submit activities, earn points and choose rewards."
              onPress={() => setMode("CHILD_LOGIN")}
            />
          </>
        ) : (
          <>
            {mode === "PARENT_REGISTER" ? (
              <>
                <Field label="Household name" value={form.familyName ?? ""} onChangeText={(v) => update("familyName", v)} />
                <Field label="Your name" value={form.displayName ?? ""} onChangeText={(v) => update("displayName", v)} />
              </>
            ) : null}
            {mode !== "CHILD_LOGIN" ? (
              <>
                <Field label="Email" autoCapitalize="none" keyboardType="email-address" value={form.email ?? ""} onChangeText={(v) => update("email", v)} />
                <Field
                  label={mode === "PARENT_REGISTER" ? "Password (at least 10 characters)" : "Password"}
                  secureTextEntry
                  value={form.password ?? ""}
                  onChangeText={(v) => update("password", v)}
                />
              </>
            ) : (
              <>
                <Field label="Household code" autoCapitalize="characters" maxLength={6} value={form.familyCode ?? ""} onChangeText={(v) => update("familyCode", v.toUpperCase())} />
                <Field label="Username" autoCapitalize="none" value={form.username ?? ""} onChangeText={(v) => update("username", v)} />
                <Field label="PIN" keyboardType="number-pad" secureTextEntry maxLength={6} value={form.pin ?? ""} onChangeText={(v) => update("pin", v)} />
              </>
            )}
            <ErrorText message={error} />
            <Button title={mode === "PARENT_REGISTER" ? "Create household" : "Sign in"} onPress={submit} loading={busy} />
            {mode === "PARENT_LOGIN" ? (
              <Button title="Create a parent account" variant="ghost" onPress={() => setMode("PARENT_REGISTER")} />
            ) : null}
            {mode === "PARENT_REGISTER" ? (
              <Button title="I already have an account" variant="ghost" onPress={() => setMode("PARENT_LOGIN")} />
            ) : null}
            <Button title="Back" variant="secondary" onPress={() => { setMode("CHOOSER"); setError(""); }} />
          </>
        )}
      </Card>
    </Screen>
  );
}

function RoleCard({
  icon,
  title,
  text,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  text: string;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.role, pressed && styles.pressed]}>
      <View style={styles.roleIcon}><Ionicons name={icon} size={27} color={colors.cocoa} /></View>
      <View style={styles.roleText}>
        <Text style={styles.roleTitle}>{title}</Text>
        <Text style={styles.roleBody}>{text}</Text>
      </View>
      <Ionicons name="arrow-forward" size={22} color={colors.peach} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { justifyContent: "center", gap: spacing.xl },
  brand: { alignItems: "center", gap: spacing.sm, paddingTop: spacing.xl },
  mark: { width: 68, height: 68, borderRadius: 24, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center", transform: [{ rotate: "-7deg" }] },
  brandName: { color: colors.cocoa, fontWeight: "900", fontSize: 30 },
  tagline: { color: colors.muted, fontSize: 16, textAlign: "center", maxWidth: 320 },
  panel: { padding: spacing.lg, gap: spacing.md },
  role: { minHeight: 92, padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: spacing.md },
  roleIcon: { width: 48, height: 48, borderRadius: 16, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  roleText: { flex: 1, gap: 4 },
  roleTitle: { color: colors.cocoa, fontSize: 17, fontWeight: "900" },
  roleBody: { color: colors.muted, lineHeight: 19 },
  pressed: { opacity: 0.72 },
});
