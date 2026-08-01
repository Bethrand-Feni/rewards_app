import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, ErrorText, Field, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";

type Mode = "LOGIN" | "REGISTER";

export default function AuthScreen() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>("LOGIN");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const update = (key: string, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const finish = () => router.replace("/");
  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (mode === "REGISTER") {
        if ((form.password ?? "").length < 10) {
          throw new Error("Password must be at least 10 characters.");
        }
        await auth.accountRegister({
          display_name: form.displayName ?? "",
          email: form.email ?? "",
          password: form.password ?? "",
        });
      } else {
        await auth.accountLogin(form.email ?? "", form.password ?? "");
      }
      finish();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not continue");
    } finally {
      setBusy(false);
    }
  };

  const submitGoogle = async () => {
    setBusy(true);
    setError("");
    try {
      await auth.googleSignIn();
      finish();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in with Google");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen contentStyle={styles.screen}>
      <View style={styles.brand}>
        <View style={styles.mark}><Ionicons name="star" size={30} color={colors.cocoa} /></View>
        <Text style={styles.brandName}>Sibling Rewards</Text>
        <Text style={styles.tagline}>{mode === "LOGIN" ? "Sign in" : "Create your account"}</Text>
      </View>

      <Card style={styles.panel}>
        {mode === "REGISTER" ? (
          <Field label="Your name" value={form.displayName ?? ""} onChangeText={(value) => update("displayName", value)} />
        ) : null}
        <Field label="Email" autoCapitalize="none" keyboardType="email-address" value={form.email ?? ""} onChangeText={(value) => update("email", value)} />
        <Field label={mode === "REGISTER" ? "Password (at least 10 characters)" : "Password"} secureTextEntry value={form.password ?? ""} onChangeText={(value) => update("password", value)} />
        <ErrorText message={error} />
        <Button title={mode === "REGISTER" ? "Create account" : "Sign in"} onPress={submit} loading={busy} />

        <View style={styles.divider}><View style={styles.line} /><Text style={styles.or}>or</Text><View style={styles.line} /></View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Continue with Google"
          disabled={busy}
          onPress={submitGoogle}
          style={({ pressed }) => [styles.googleButton, pressed && styles.pressed]}
        >
          <Ionicons name="logo-google" size={25} color={colors.cocoa} />
        </Pressable>
        <Text style={styles.googleLabel}>Continue with Google</Text>

        <View style={styles.switchRow}>
          <Text style={styles.switchText}>{mode === "LOGIN" ? "New here?" : "Already have an account?"}</Text>
          <Pressable onPress={() => { setMode(mode === "LOGIN" ? "REGISTER" : "LOGIN"); setError(""); }}>
            <Text style={styles.switchLink}>{mode === "LOGIN" ? "Create account" : "Sign in"}</Text>
          </Pressable>
        </View>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: { justifyContent: "center", gap: spacing.xl },
  brand: { alignItems: "center", gap: spacing.sm, paddingTop: spacing.xl },
  mark: { width: 68, height: 68, borderRadius: 24, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center", transform: [{ rotate: "-7deg" }] },
  brandName: { color: colors.cocoa, fontWeight: "900", fontSize: 30 },
  tagline: { color: colors.muted, fontSize: 17, textAlign: "center" },
  panel: { padding: spacing.lg, gap: spacing.md },
  divider: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  line: { flex: 1, height: 1, backgroundColor: colors.border },
  or: { color: colors.muted, fontWeight: "700" },
  googleButton: { width: 54, height: 54, borderRadius: radius.md, borderWidth: 1, borderColor: colors.peach, alignSelf: "center", alignItems: "center", justifyContent: "center", backgroundColor: colors.white },
  googleLabel: { color: colors.muted, textAlign: "center", marginTop: -spacing.sm },
  switchRow: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: spacing.sm, flexWrap: "wrap" },
  switchText: { color: colors.muted },
  switchLink: { color: colors.peach, fontWeight: "900" },
  pressed: { opacity: 0.68 },
});
