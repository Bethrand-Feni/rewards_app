import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { File } from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/AuthContext";
import { Button, Card, ErrorText, Field, Header, Screen } from "@/components";
import { colors, radius, spacing } from "@/theme";

export default function Submit() {
  const params = useLocalSearchParams<{ choreId?: string; title?: string; submissionId?: string }>();
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(params.title ?? "");
  const [description, setDescription] = useState("");
  const [image, setImage] = useState<{ uri: string; name: string; type: string } | null>(null);
  const [error, setError] = useState("");
  const isResubmission = Boolean(params.submissionId);
  const isChore = Boolean(params.choreId);

  const pickImage = async (camera: boolean) => {
    setError("");
    const permission = camera
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setError(`Allow ${camera ? "camera" : "photo"} access to attach proof.`);
      return;
    }
    try {
      const result = camera
        ? await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.75 })
        : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.75 });
      if (result.canceled) return;
      const asset = result.assets[0];
      setImage({
        uri: asset.uri,
        name: asset.fileName ?? `proof-${Date.now()}.jpg`,
        type: asset.mimeType ?? "image/jpeg",
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not prepare the photo.");
    }
  };

  const submit = useMutation({
    mutationFn: async () => {
      if (!image) throw new Error("Add a photo before submitting.");
      const form = new FormData();
      form.append("image", new File(image.uri), image.name);
      form.append("description", description);
      if (!isResubmission) {
        form.append("submission_type", isChore ? "CHORE" : "OTHER_ACTIVITY");
        form.append("title", isChore ? params.title ?? title : title);
        if (params.choreId) form.append("chore_id", params.choreId);
      }
      const path = isResubmission ? `/submissions/${params.submissionId}/resubmit` : "/submissions";
      return api(path, { method: "POST", body: form });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      router.replace("/child/activity");
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "Submission failed"),
  });

  return (
    <Screen>
      <Header eyebrow={isResubmission ? "Try again" : "Photo proof"} title={isResubmission ? "Resubmit activity" : isChore ? params.title ?? "Submit chore" : "Submit an activity"} />
      <Card>
        {!isChore && !isResubmission ? <Field label="Activity title" value={title} onChangeText={setTitle} placeholder="What did you help with?" /> : null}
        <Field label={isResubmission ? "What did you change?" : "Short note"} multiline value={description} onChangeText={setDescription} placeholder="Add useful context for the review." />
        <Text style={styles.label}>Proof photo</Text>
        {image ? (
          <Image source={{ uri: image.uri }} style={styles.preview} />
        ) : (
          <View style={styles.placeholder}><Ionicons name="camera-outline" size={38} color={colors.peach} /><Text style={styles.placeholderText}>One clear photo is required</Text></View>
        )}
        <View style={styles.actions}>
          <Pressable onPress={() => pickImage(true)} style={styles.photoButton}><Ionicons name="camera" size={22} color={colors.cocoa} /><Text style={styles.photoText}>Take photo</Text></Pressable>
          <Pressable onPress={() => pickImage(false)} style={styles.photoButton}><Ionicons name="images" size={22} color={colors.cocoa} /><Text style={styles.photoText}>Choose photo</Text></Pressable>
        </View>
        <Text style={styles.help}>The app compresses your image before upload.</Text>
        <ErrorText message={error} />
        <Button title={isResubmission ? "Send updated proof" : "Send for review"} loading={submit.isPending} disabled={!image || (!isChore && !isResubmission && title.trim().length < 2)} onPress={() => submit.mutate()} />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  label: { color: colors.cocoa, fontWeight: "800", fontSize: 13 },
  preview: { width: "100%", height: 260, borderRadius: radius.md, backgroundColor: colors.border },
  placeholder: { height: 210, borderRadius: radius.md, borderWidth: 2, borderStyle: "dashed", borderColor: colors.border, alignItems: "center", justifyContent: "center", gap: spacing.sm, backgroundColor: colors.white },
  placeholderText: { color: colors.muted, fontWeight: "700" },
  actions: { flexDirection: "row", gap: spacing.sm },
  photoButton: { flex: 1, minHeight: 52, borderRadius: radius.sm, backgroundColor: colors.sun, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm },
  photoText: { color: colors.cocoa, fontWeight: "900" },
  help: { color: colors.muted, fontSize: 12, textAlign: "center" },
});
