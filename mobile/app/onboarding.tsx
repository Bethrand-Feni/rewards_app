import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, ErrorText, Field, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";

type Mode = "CHOOSER" | "CREATE" | "JOIN";

export default function OnboardingScreen() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>("CHOOSER");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [familyName, setFamilyName] = useState("");
  const [familyCode, setFamilyCode] = useState("");
  const [joinPin, setJoinPin] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (mode === "CREATE") {
        await auth.createHousehold(familyName, Intl.DateTimeFormat().resolvedOptions().timeZone || "Africa/Johannesburg");
      } else {
        await auth.joinHousehold(familyCode, joinPin);
      }
      router.replace("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not continue");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen contentStyle={styles.screen}>
      <View style={styles.header}>
        <View style={styles.mark}><Ionicons name="star" size={28} color={colors.cocoa} /></View>
        <Text style={styles.title}>Welcome, {auth.user?.display_name}</Text>
        <Text style={styles.subtitle}>Create a household or join one with an invitation.</Text>
      </View>
      <Card style={styles.panel}>
        {mode === "CHOOSER" ? (
          <>
            <Choice icon="home-outline" title="Create a household" text="Start a new family and become its first parent." onPress={() => setMode("CREATE")} />
            <Choice icon="key-outline" title="Join a household" text="Use the family code and one-time code from your invitation." onPress={() => setMode("JOIN")} />
          </>
        ) : (
          <>
            <Pressable onPress={() => { setMode("CHOOSER"); setError(""); }} style={styles.back}><Ionicons name="arrow-back" size={21} color={colors.cocoa} /><Text style={styles.backText}>Back</Text></Pressable>
            <Text style={styles.formTitle}>{mode === "CREATE" ? "Create your household" : "Join a household"}</Text>
            {mode === "CREATE" ? (
              <Field label="Household name" value={familyName} onChangeText={setFamilyName} />
            ) : (
              <>
                <Field label="Household code" autoCapitalize="characters" maxLength={6} value={familyCode} onChangeText={(value) => setFamilyCode(value.toUpperCase())} />
                <Field label="One-time code" keyboardType="number-pad" maxLength={6} value={joinPin} onChangeText={setJoinPin} />
              </>
            )}
            <ErrorText message={error} />
            <Button title={mode === "CREATE" ? "Create household" : "Join household"} onPress={submit} loading={busy} />
          </>
        )}
      </Card>
      <Button title="Sign out" variant="ghost" onPress={auth.logout} />
    </Screen>
  );
}

function Choice({ icon, title, text, onPress }: { icon: keyof typeof Ionicons.glyphMap; title: string; text: string; onPress: () => void }) {
  return <Pressable onPress={onPress} style={({ pressed }) => [styles.choice, pressed && styles.pressed]}><View style={styles.choiceIcon}><Ionicons name={icon} size={26} color={colors.cocoa} /></View><View style={styles.grow}><Text style={styles.choiceTitle}>{title}</Text><Text style={styles.choiceText}>{text}</Text></View><Ionicons name="arrow-forward" size={22} color={colors.peach} /></Pressable>;
}

const styles = StyleSheet.create({
  screen: { justifyContent: "center", gap: spacing.xl },
  header: { alignItems: "center", gap: spacing.sm },
  mark: { width: 64, height: 64, borderRadius: 22, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  title: { color: colors.cocoa, fontSize: 27, fontWeight: "900", textAlign: "center" },
  subtitle: { color: colors.muted, fontSize: 16, textAlign: "center", maxWidth: 340 },
  panel: { padding: spacing.lg, gap: spacing.md },
  choice: { minHeight: 104, padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: spacing.md },
  choiceIcon: { width: 48, height: 48, borderRadius: 16, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  grow: { flex: 1, gap: 4 },
  choiceTitle: { color: colors.cocoa, fontSize: 17, fontWeight: "900" },
  choiceText: { color: colors.muted, lineHeight: 19 },
  back: { flexDirection: "row", gap: spacing.sm, alignItems: "center", alignSelf: "flex-start" },
  backText: { color: colors.cocoa, fontWeight: "800" },
  formTitle: { color: colors.cocoa, fontSize: 22, fontWeight: "900" },
  pressed: { opacity: 0.7 },
});
