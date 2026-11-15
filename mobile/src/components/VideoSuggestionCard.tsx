import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { T } from "@/components/ui";
import { colors, fonts, radius } from "@/lib/theme";
import { VideoSuggestion, videoMeta, videoRouteParams } from "@/lib/upgrade";

/**
 * Sohbette istenen video: Üret ekranının Video sekmesini konsept ve görselle hazır açar (web `VideoSuggestionCard`).
 * Paketinde video yoksa onLocked çağrılır (sohbette paket kartı açılır).
 */
export default function VideoSuggestionCard({ video, onLocked }: { video: VideoSuggestion; onLocked: () => void }) {
  const open = () => (video.enabled ? router.push({ pathname: "/uret", params: videoRouteParams(video) }) : onLocked());
  return (
    <View style={st.card}>
      <View style={st.icon}>
        <Ionicons name="videocam" size={18} color={colors.indigoSoft} />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <T style={{ fontFamily: fonts.bodySemi }}>Video konsepti hazır</T>
        <T variant="small" style={{ color: colors.muted }}>{videoMeta(video)}</T>
        <T variant="small" numberOfLines={2} style={{ color: colors.faint }}>{video.concept}</T>
      </View>
      <Pressable
        accessibilityRole="button"
        onPress={open}
        style={({ pressed }) => [st.btn, pressed && { opacity: 0.8 }]}
      >
        <T variant="small" style={{ fontFamily: fonts.bodySemi, color: colors.white }}>{video.enabled ? "Bu videoyu üret" : "Paketini yükselt"}</T>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  card: { flexDirection: "row", alignItems: "center", gap: 10, padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  icon: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center", backgroundColor: "#1D1C4A" },
  btn: { backgroundColor: colors.indigo, paddingHorizontal: 12, paddingVertical: 9, borderRadius: radius.pill },
});
