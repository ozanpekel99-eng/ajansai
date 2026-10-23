import Ionicons from "@expo/vector-icons/Ionicons";
import { useFocusEffect } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useCallback } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button, Card, T } from "@/components/ui";
import { useSession } from "@/lib/session";
import { colors } from "@/lib/theme";

const fmt = (iso?: string) => (iso ? new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long" }) : "");

export default function Hesap() {
  const { user, usage, refresh, signOut } = useSession();
  useFocusEffect(useCallback(() => void refresh(), [refresh]));
  const c = usage?.credits;
  const free = usage?.plan === "deneme";
  const pct = c && c.total ? Math.max(0, Math.min(1, c.period_remaining / c.total)) : 0;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
      <ScrollView contentContainerStyle={st.body}>
        <T variant="h2">Hesap</T>
        <Card style={{ gap: 4 }}>
          <T variant="h3">{user?.name || "ajansAI kullanıcısı"}</T>
          <T variant="muted">{user?.email}</T>
        </Card>

        <Card style={{ gap: 12 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <T variant="h3">{usage?.plan_name ?? "…"} paketi</T>
            {!free && usage?.period_end ? <T variant="small" style={{ color: colors.muted }}>{fmt(usage.period_end)} yenilenir</T> : null}
          </View>
          {c && !free ? (
            <>
              <T>{c.remaining.toLocaleString("tr-TR")} kredin kaldı{c.extra ? ` (${c.extra.toLocaleString("tr-TR")} ek kredi dahil)` : ""}</T>
              <View style={st.meter}><View style={[st.fill, { width: `${pct * 100}%` }]} /></View>
            </>
          ) : (
            <T variant="muted">Ücretsiz pakette günlük mesaj ve aylık görsel hakkın var. Video ve reklam için bir paket seç.</T>
          )}
          <Button title={free ? "Paket seç" : "Paketler ve ek kredi"} onPress={() => Alert.alert("Paketler", "Uygulama içi satın alma bir sonraki sürümde geliyor.")} />
        </Card>

        <Card style={{ gap: 0, padding: 0 }}>
          <Row icon="document-text-outline" title="Kullanım Koşulları" onPress={() => WebBrowser.openBrowserAsync("https://www.ajansai.tr/kosullar")} />
          <Row icon="shield-checkmark-outline" title="Gizlilik Politikası" onPress={() => WebBrowser.openBrowserAsync("https://www.ajansai.tr/gizlilik")} />
          <Row icon="mail-outline" title="Destek: support@ajansai.tr" onPress={() => WebBrowser.openBrowserAsync("https://www.ajansai.tr/iletisim")} last />
        </Card>

        <Button title="Çıkış yap" variant="ghost" onPress={() => signOut()} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ icon, title, onPress, last }: { icon: keyof typeof Ionicons.glyphMap; title: string; onPress: () => void; last?: boolean }) {
  return (
    <Pressable onPress={onPress} style={[st.row, !last && { borderBottomWidth: 1, borderBottomColor: colors.line }]}>
      <Ionicons name={icon} size={20} color={colors.muted} />
      <T style={{ flex: 1 }}>{title}</T>
      <Ionicons name="chevron-forward" size={18} color={colors.faint} />
    </Pressable>
  );
}

const st = StyleSheet.create({
  body: { padding: 18, gap: 16, paddingBottom: 40 },
  meter: { height: 8, borderRadius: 4, backgroundColor: colors.surface2, overflow: "hidden" },
  fill: { height: 8, backgroundColor: colors.indigo },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 15 },
});
