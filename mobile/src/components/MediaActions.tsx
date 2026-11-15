import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from "react-native";

import { T } from "@/components/ui";
import { AdKind, adAction } from "@/lib/adShortcut";
import { saveToGallery, shareMedia } from "@/lib/media";
import { useSession } from "@/lib/session";
import { colors } from "@/lib/theme";

type Kind = "save" | "share" | "ad";

/**
 * Görsel/video altındaki "Kaydet", "Paylaş" ve (ad verilirse) "Reklam ver" düğmeleri.
 * "Reklam ver" dosyayı ajansai.tr'deki Reklam sayfasına taşır (web ile aynı bağlantı biçimi).
 */
export default function MediaActions({ url, ad }: { url: string; ad?: { kind: AdKind; concept?: string } }) {
  const { usage } = useSession();
  const [busy, setBusy] = useState<Kind | null>(null);

  const advertise = async () => {
    if (!ad) return;
    const a = adAction(url, ad.kind, ad.concept ?? "", usage?.ads_enabled);
    if (a.type === "invalid") {
      Alert.alert("Bu dosyayla reklam verilemiyor", "Dosyayı yeniden üretip tekrar dene.");
      return;
    }
    if (a.type === "upgrade") {
      Alert.alert("Reklam vermek paketlere dahil", "Ürettiğin görsel ve videolarla tek tıkla Instagram reklamı vermek için bir paket seç.", [
        { text: "Vazgeç", style: "cancel" },
        { text: "Paketleri gör", onPress: () => router.push("/hesap") },
      ]);
      return;
    }
    await WebBrowser.openBrowserAsync(a.url);
  };

  const run = async (kind: Kind) => {
    setBusy(kind);
    try {
      if (kind === "save") {
        const ok = await saveToGallery(url);
        Alert.alert(ok ? "Galeriye kaydedildi" : "Galeri izni gerekli", ok ? "" : "Ayarlar'dan ajansAI'a fotoğraf izni verebilirsin.");
      } else if (kind === "share") {
        await shareMedia(url);
      } else {
        await advertise();
      }
    } catch {
      Alert.alert("İşlem tamamlanamadı", "İnternet bağlantını kontrol edip tekrar dene.");
    } finally {
      setBusy(null);
    }
  };

  const buttons: { k: Kind; icon: keyof typeof Ionicons.glyphMap; label: string }[] = [
    { k: "save", icon: "download-outline", label: "Kaydet" },
    { k: "share", icon: "share-outline", label: "Paylaş" },
  ];
  if (ad) buttons.push({ k: "ad", icon: "megaphone-outline", label: "Reklam ver" });

  return (
    <View style={st.row}>
      {buttons.map(({ k, icon, label }) => (
        <Pressable
          key={k}
          onPress={() => run(k)}
          style={[st.btn, k === "ad" && st.adBtn]}
          accessibilityRole="button"
          accessibilityLabel={k === "ad" ? "Bu dosyayla Instagram reklamı ver" : label}
          disabled={!!busy}
        >
          {busy === k ? <ActivityIndicator size="small" color={colors.fg} /> : <Ionicons name={icon} size={17} color={k === "ad" ? colors.white : colors.fg} />}
          <T variant="small" style={k === "ad" ? { color: colors.white } : undefined}>{label}</T>
        </Pressable>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  btn: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.line },
  adBtn: { backgroundColor: colors.indigo, borderColor: colors.indigo },
});
