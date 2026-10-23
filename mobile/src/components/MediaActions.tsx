import Ionicons from "@expo/vector-icons/Ionicons";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from "react-native";

import { T } from "@/components/ui";
import { saveToGallery, shareMedia } from "@/lib/media";
import { colors } from "@/lib/theme";

/** Görsel/video altındaki "Kaydet" ve "Paylaş" düğmeleri. */
export default function MediaActions({ url }: { url: string }) {
  const [busy, setBusy] = useState<"save" | "share" | null>(null);
  const run = async (kind: "save" | "share") => {
    setBusy(kind);
    try {
      if (kind === "save") {
        const ok = await saveToGallery(url);
        Alert.alert(ok ? "Galeriye kaydedildi" : "Galeri izni gerekli", ok ? "" : "Ayarlar'dan ajansAI'a fotoğraf izni verebilirsin.");
      } else {
        await shareMedia(url);
      }
    } catch {
      Alert.alert("İşlem tamamlanamadı", "İnternet bağlantını kontrol edip tekrar dene.");
    } finally {
      setBusy(null);
    }
  };
  return (
    <View style={st.row}>
      {(["save", "share"] as const).map((k) => (
        <Pressable key={k} onPress={() => run(k)} style={st.btn} accessibilityRole="button" disabled={!!busy}>
          {busy === k ? <ActivityIndicator size="small" color={colors.fg} /> : <Ionicons name={k === "save" ? "download-outline" : "share-outline"} size={17} color={colors.fg} />}
          <T variant="small">{k === "save" ? "Kaydet" : "Paylaş"}</T>
        </Pressable>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: "row", gap: 8 },
  btn: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.line },
});
