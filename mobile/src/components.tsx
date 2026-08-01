import { Ionicons } from "@expo/vector-icons";
import { useEffect, useRef, type PropsWithChildren, type ReactNode, type RefObject } from "react";
import {
  ActivityIndicator,
  Animated,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  type TextStyle,
  View,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, radius, spacing } from "./theme";

export function Screen({
  children,
  scroll = true,
  scrollEnabled = true,
  contentStyle,
  scrollRef,
}: PropsWithChildren<{
  scroll?: boolean;
  scrollEnabled?: boolean;
  contentStyle?: ViewStyle;
  scrollRef?: RefObject<ScrollView | null>;
}>) {
  const content = <View style={[styles.screenContent, contentStyle]}>{children}</View>;
  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Wave />
      {scroll ? (
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.scroll}
          overScrollMode="never"
          scrollEnabled={scrollEnabled}
        >
          {content}
        </ScrollView>
      ) : content}
    </SafeAreaView>
  );
}

export function Wave() {
  return (
    <View pointerEvents="none" style={styles.waveWrap}>
      <View style={[styles.wave, styles.waveOne]} />
      <View style={[styles.wave, styles.waveTwo]} />
    </View>
  );
}

export function Header({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <View style={styles.header}>
      <View style={styles.headerText}>
        {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
        <Text style={styles.title}>{title}</Text>
      </View>
      {action}
    </View>
  );
}

export function Card({
  children,
  style,
}: PropsWithChildren<{ style?: ViewStyle | ViewStyle[] }>) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Button({
  title,
  onPress,
  variant = "primary",
  disabled,
  loading,
  icon,
}: {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean;
  loading?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        styles[`button_${variant}`],
        (disabled || loading) && styles.buttonDisabled,
        pressed && styles.pressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === "primary" ? colors.cocoa : colors.peach} />
      ) : (
        <>
          {icon ? <Ionicons name={icon} size={18} color={variant === "primary" ? colors.cocoa : colors.peach} /> : null}
          <Text style={[styles.buttonText, styles[`buttonText_${variant}`]]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

export function IconButton({
  icon,
  label,
  onPress,
  variant = "secondary",
  loading,
  disabled,
  compact = false,
  compactSize = "small",
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  variant?: "secondary" | "danger";
  loading?: boolean;
  disabled?: boolean;
  compact?: boolean;
  compactSize?: "small" | "medium";
}) {
  const color = variant === "danger" ? colors.danger : colors.cocoa;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.iconButton,
        !compact && variant === "danger" && styles.iconButtonDanger,
        compact && styles.iconButtonCompact,
        compact && compactSize === "medium" && styles.iconButtonCompactMedium,
        (disabled || loading) && styles.buttonDisabled,
        pressed && styles.pressed,
      ]}
    >
      {loading ? <ActivityIndicator color={color} size="small" /> : <Ionicons name={icon} size={compact ? compactSize === "medium" ? 20 : 18 : 21} color={color} />}
    </Pressable>
  );
}

export function FeedbackBanner({
  message,
  tone = "success",
}: {
  message?: string | null;
  tone?: "success" | "info";
}) {
  if (!message) return null;
  return (
    <View accessibilityLiveRegion="polite" style={[styles.feedback, tone === "info" && styles.feedbackInfo]}>
      <Ionicons name={tone === "success" ? "checkmark-circle" : "sparkles"} size={20} color={colors.cocoa} />
      <Text style={styles.feedbackText}>{message}</Text>
    </View>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        placeholderTextColor={colors.muted}
        style={[styles.input, props.multiline && styles.multiline]}
        {...props}
      />
    </View>
  );
}

export function Pill({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "success" | "danger" | "info";
}) {
  return (
    <View style={[styles.pill, styles[`pill_${tone}`]]}>
      <Text style={[styles.pillText, styles[`pillText_${tone}`]]}>{label.replaceAll("_", " ")}</Text>
    </View>
  );
}

export function Empty({ title, message }: { title: string; message: string }) {
  return (
    <Card style={styles.empty}>
      <Ionicons name="sparkles-outline" size={28} color={colors.peach} />
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.body}>{message}</Text>
    </Card>
  );
}

export function ErrorText({ message }: { message?: string | null }) {
  return message ? <Text style={styles.error}>{message}</Text> : null;
}

export function Loading() {
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.peach} size="large" />
    </View>
  );
}

export function AnimatedNumber({ value, style }: { value: number; style?: TextStyle }) {
  const scale = useRef(new Animated.Value(1)).current;
  const previous = useRef(value);

  useEffect(() => {
    if (previous.current === value) return;
    previous.current = value;
    Animated.sequence([
      Animated.spring(scale, { toValue: 1.16, useNativeDriver: true, speed: 24 }),
      Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 18 }),
    ]).start();
  }, [scale, value]);

  return <Animated.Text style={[style, { transform: [{ scale }] }]}>{value}</Animated.Text>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas },
  scroll: { flexGrow: 1 },
  screenContent: { flex: 1, padding: spacing.md, gap: spacing.md, paddingBottom: 110 },
  waveWrap: { position: "absolute", right: -45, top: -80, width: 220, height: 220 },
  wave: { position: "absolute", borderRadius: 120, borderWidth: 22, backgroundColor: "transparent" },
  waveOne: { width: 190, height: 190, borderColor: colors.sun, right: 0, top: 0 },
  waveTwo: { width: 140, height: 140, borderColor: colors.peach, right: 26, top: 26 },
  header: { minHeight: 72, flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", gap: spacing.md },
  headerText: { flex: 1, gap: 3 },
  eyebrow: { color: colors.peach, fontSize: 13, fontWeight: "800", letterSpacing: 0.8, textTransform: "uppercase" },
  title: { color: colors.cocoa, fontSize: 30, lineHeight: 34, fontWeight: "900" },
  card: {
    backgroundColor: colors.cream,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.sm,
  },
  button: {
    minHeight: 48,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacing.sm,
  },
  iconButton: { width: 44, height: 44, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.sun, alignItems: "center", justifyContent: "center" },
  iconButtonDanger: { backgroundColor: "#FBE9E5", borderColor: "#E9B7AE" },
  iconButtonCompact: { width: 36, height: 36, borderWidth: 0, borderColor: "transparent", backgroundColor: "transparent", borderRadius: 10 },
  iconButtonCompactMedium: { width: 40, height: 40 },
  feedback: { minHeight: 48, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.peach, backgroundColor: "#FFF0DF", paddingHorizontal: spacing.md, paddingVertical: 11, flexDirection: "row", alignItems: "center", gap: spacing.sm },
  feedbackInfo: { backgroundColor: colors.sun, borderColor: "#E0B84E" },
  feedbackText: { flex: 1, color: colors.cocoa, fontWeight: "800", lineHeight: 19 },
  button_primary: { backgroundColor: colors.peach },
  button_secondary: { backgroundColor: colors.cream, borderWidth: 1, borderColor: colors.peach },
  button_ghost: { backgroundColor: "transparent" },
  button_danger: { backgroundColor: "#F8E4E0", borderWidth: 1, borderColor: colors.danger },
  buttonDisabled: { opacity: 0.45 },
  pressed: { opacity: 0.72 },
  buttonText: { fontWeight: "900", fontSize: 15 },
  buttonText_primary: { color: colors.cocoa },
  buttonText_secondary: { color: colors.peach },
  buttonText_ghost: { color: colors.peach },
  buttonText_danger: { color: colors.danger },
  fieldWrap: { gap: 6 },
  label: { color: colors.cocoa, fontWeight: "800", fontSize: 13 },
  input: {
    minHeight: 48,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.white,
    color: colors.cocoa,
    paddingHorizontal: 14,
    fontSize: 16,
  },
  multiline: { minHeight: 88, paddingTop: 12, textAlignVertical: "top" },
  pill: { alignSelf: "flex-start", borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 5, backgroundColor: "#EEE6D7" },
  pill_neutral: { backgroundColor: "#EEE6D7" },
  pill_success: { backgroundColor: "#DCEDE1" },
  pill_danger: { backgroundColor: "#F5DEDA" },
  pill_info: { backgroundColor: "#DCEBF0" },
  pillText: { fontSize: 11, fontWeight: "900", textTransform: "uppercase", color: colors.muted },
  pillText_neutral: { color: colors.muted },
  pillText_success: { color: colors.success },
  pillText_danger: { color: colors.danger },
  pillText_info: { color: colors.info },
  empty: { alignItems: "center", paddingVertical: spacing.xl },
  emptyTitle: { color: colors.cocoa, fontSize: 18, fontWeight: "900" },
  body: { color: colors.muted, lineHeight: 20, textAlign: "center" },
  error: { color: colors.danger, fontWeight: "700" },
  loading: { flex: 1, minHeight: 220, alignItems: "center", justifyContent: "center" },
});
