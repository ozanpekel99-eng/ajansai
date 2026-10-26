import Ionicons from "@expo/vector-icons/Ionicons";
import { Image } from "expo-image";
import { router, useFocusEffect } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button, Card, ErrorText, T } from "@/components/ui";
import { AdRow, adsManagerUrl, isRunning, isVideoUrl, money, num, OBJECTIVE_LABELS, Range, RANGES, statusOf, StatusTone, totals, WEB_ADS_URL } from "@/lib/ads";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import { colors, fonts, radius } from "@/lib/theme";

const TONE: Record<StatusTone, { bg: string; fg: string }> = {
  ok: { bg: "rgba(61,220,151,0.14)", fg: colors.ok },
  pending: { bg: colors.surface2, fg: colors.muted },
  bad: { bg: "rgba(255,92,92,0.14)", fg: colors.danger },
};

export default function Reklam() {
  const { usage, refresh } = useSession();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [statusError, setStatusError] = useState("");

  const checkStatus = useCallback(async () => {
    try {
      const d = await api<{ connected: boolean }>("/api/ads/meta/status");
      setConnected(d.connected);
      setStatusError("");
    } catch (e) {
      setStatusError((e as ApiError).message);
      setConnected((c) => c ?? false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void refresh();
      void checkStatus();
    }, [refresh, checkStatus]),
  );

  // Bağlantı web'de kurulur; tarayıcı kapanınca durumu yeniden kontrol ederiz
  const connectOnWeb = async () => {
    await WebBrowser.openBrowserAsync(WEB_ADS_URL);
    await checkStatus();
  };

  const disconnect = () =>
    Alert.alert("Meta bağlantısı kaldırılsın mı?", "Reklamların Meta'da kalır; ajansAI'dan görmek için tekrar bağlaman gerekir.", [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Kaldır",
        style: "destructive",
        onPress: async () => {
          try {
            await api("/api/ads/meta/connection", { method: "DELETE" });
          } finally {
            await checkStatus();
          }
        },
      },
    ]);

  let body;
  if (usage && !usage.ads_enabled) {
    body = (
      <Card style={{ gap: 12 }}>
        <Ionicons name="lock-closed-outline" size={22} color={colors.indigoSoft} />
        <T variant="h3">Instagram reklamları Pro ve Advanced paketlerinde</T>
        <T variant="muted">Ürettiğin görsel ve videoları tek tıkla Instagram reklamına çevirmek için paketini yükselt.</T>
        <Button title="Paketleri gör" onPress={() => router.push("/hesap")} />
      </Card>
    );
  } else if (connected === null) {
    body = <ActivityIndicator style={{ marginTop: 40 }} color={colors.indigoSoft} />;
  } else if (!connected) {
    body = (
      <Card style={{ gap: 12 }}>
        <T variant="h3">Meta hesabını bağla</T>
        <T variant="muted">
          Facebook hesabınla giriş yaparsın; reklam bütçesi kendi reklam hesabından harcanır. Reklamlar yalnızca Instagram'da gösterilir ve sen "Yayına al" demeden yayına girmez.
        </T>
        <T variant="small" style={{ color: colors.muted }}>
          Bağlantıyı şimdilik ajansai.tr üzerinden kuruyoruz: açılan sayfada aynı hesapla giriş yap ve "Meta ile bağlan"a dokun. Bitince bu ekrana dön.
        </T>
        <ErrorText>{statusError}</ErrorText>
        <Button title="Meta ile bağlan" onPress={connectOnWeb} />
        <Button title="Bağladım, kontrol et" variant="ghost" onPress={checkStatus} />
      </Card>
    );
  } else {
    body = <AdList onDisconnect={disconnect} />;
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
      {connected && usage?.ads_enabled !== false ? (
        body
      ) : (
        <ScrollView contentContainerStyle={st.body}>
          <T variant="h2">Reklam</T>
          {body}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

/* ---------------- Reklamlarım ---------------- */

function AdList({ onDisconnect }: { onDisconnect: () => void }) {
  const [ads, setAds] = useState<AdRow[] | null>(null);
  const [range, setRange] = useState<Range>("today");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState<Date | null>(null);
  const rangeRef = useRef(range);
  rangeRef.current = range;

  const load = useCallback(async (r: Range) => {
    setLoading(true);
    try {
      const d = await api<{ ads: AdRow[] }>(`/api/ads/meta/ads?range=${r}`);
      if (rangeRef.current !== r) return; // bu arada aralık değiştiyse eski yanıtı yok say
      setAds(d.ads);
      setUpdated(new Date());
      setError("");
    } catch (e) {
      setError((e as ApiError).message);
      setAds((cur) => cur ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(range);
  }, [range, load]);

  // Ekran açıkken her dakika canlı yenilenir
  useFocusEffect(
    useCallback(() => {
      const t = setInterval(() => void load(rangeRef.current), 60000);
      return () => clearInterval(t);
    }, [load]),
  );

  const run = async (ad: AdRow, action: "publish" | "pause") => {
    setBusy(ad.id);
    setError("");
    try {
      await api(`/api/ads/meta/ads/${ad.id}/${action}`, { method: "POST" });
      await load(rangeRef.current);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  };

  const act = (ad: AdRow, action: "publish" | "pause") => {
    if (action === "pause") return void run(ad, action);
    const budget = `${ad.budget_type === "lifetime" ? "Toplam" : "Günlük"} ${money(ad.daily_budget, ad.currency)}`;
    Alert.alert("Reklam yayına alınsın mı?", `Bütçe Meta reklam hesabından harcanmaya başlar (${budget}).`, [
      { text: "Vazgeç", style: "cancel" },
      { text: "Yayına al", onPress: () => void run(ad, action) },
    ]);
  };

  const sum = ads ? totals(ads) : null;
  const currency = ads?.[0]?.currency || "TRY";

  return (
    <ScrollView
      contentContainerStyle={st.body}
      refreshControl={<RefreshControl refreshing={loading && ads !== null} onRefresh={() => load(range)} tintColor={colors.indigoSoft} />}
    >
      <View style={st.titleRow}>
        <T variant="h2">Reklamlarım</T>
        <Pressable onPress={onDisconnect} hitSlop={10}>
          <T variant="small" style={{ color: colors.muted }}>Bağlantıyı kaldır</T>
        </Pressable>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        {RANGES.map((r) => (
          <Pressable key={r.value} onPress={() => setRange(r.value)} style={[st.chip, range === r.value && st.chipOn]}>
            <T variant="small" style={{ color: range === r.value ? colors.white : colors.muted, fontFamily: fonts.bodyMedium }}>{r.label}</T>
          </Pressable>
        ))}
      </ScrollView>
      <T variant="small" style={{ color: colors.faint }}>
        {loading ? "Güncelleniyor…" : updated ? `Son güncelleme ${updated.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })} · her dakika yenilenir` : ""}
      </T>
      <ErrorText>{error}</ErrorText>

      {ads === null ? (
        <View style={{ alignItems: "center", gap: 10, marginTop: 30 }}>
          <ActivityIndicator color={colors.indigoSoft} />
          <T variant="muted">Reklamların ve sonuçları Meta'dan alınıyor…</T>
        </View>
      ) : ads.length === 0 ? (
        <Card style={{ gap: 10 }}>
          <T variant="h3">Henüz reklam oluşturmadın</T>
          <T variant="muted">İlk reklamını ajansai.tr'deki Reklam sayfasından oluşturabilirsin; durumunu ve sonuçlarını burada canlı görürsün. Uygulamadan reklam oluşturma çok yakında.</T>
          <Button title="Web'de reklam oluştur" variant="ghost" onPress={() => WebBrowser.openBrowserAsync(WEB_ADS_URL)} />
        </Card>
      ) : (
        <>
          {sum && (
            <View style={st.summary}>
              <Kpi label="Harcama" value={money(sum.spend, currency)} />
              <Kpi label="Sonuç" value={num(sum.results)} />
              <Kpi label="Erişim" value={num(sum.reach)} />
              <Kpi label="Gösterim" value={num(sum.impressions)} />
            </View>
          )}
          {ads.map((ad) => (
            <AdCard key={ad.id} ad={ad} busy={busy === ad.id} onAct={act} />
          ))}
        </>
      )}
    </ScrollView>
  );
}

function AdCard({ ad, busy, onAct }: { ad: AdRow; busy: boolean; onAct: (ad: AdRow, action: "publish" | "pause") => void }) {
  const st0 = statusOf(ad.status);
  const tone = TONE[st0.tone];
  const i = ad.insights;
  const running = isRunning(ad.status);
  return (
    <Card style={{ gap: 12 }}>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <View style={st.thumb}>
          {ad.media_url && !isVideoUrl(ad.media_url) ? (
            <Image source={{ uri: ad.media_url }} style={StyleSheet.absoluteFill} contentFit="cover" transition={150} />
          ) : (
            <Ionicons name={ad.media_url ? "videocam-outline" : "image-outline"} size={22} color={colors.faint} />
          )}
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <T variant="h3" numberOfLines={2}>{ad.name}</T>
          <View style={[st.pill, { backgroundColor: tone.bg }]}>
            <T variant="small" style={{ color: tone.fg, fontFamily: fonts.bodyMedium }}>{st0.label}</T>
          </View>
          <T variant="small" style={{ color: colors.muted }}>
            {OBJECTIVE_LABELS[ad.objective] ?? ad.objective} · {ad.budget_type === "lifetime" ? "Toplam" : "Günlük"} {money(ad.daily_budget, ad.currency)}
          </T>
        </View>
      </View>
      {ad.review ? <T variant="small" style={{ color: colors.danger }}>Meta: {ad.review}</T> : null}
      {i ? (
        <View style={st.kpis}>
          <Kpi main label={i.result_label} value={num(i.results)} note={i.results ? `${money(i.cost_per_result, ad.currency)} / sonuç` : "—"} />
          <Kpi label="Harcama" value={money(i.spend, ad.currency)} />
          <Kpi label="Erişim" value={num(i.reach)} />
          <Kpi label="Gösterim" value={num(i.impressions)} />
          <Kpi label="Bağlantı tıklaması" value={num(i.link_clicks)} />
          <Kpi label="TO (CTR)" value={`%${num(i.ctr, 2)}`} />
          <Kpi label="TBM (CPC)" value={i.cpc ? money(i.cpc, ad.currency) : "—"} />
        </View>
      ) : ad.error ? (
        <T variant="small" style={{ color: colors.danger }}>{ad.error}</T>
      ) : null}
      <View style={{ flexDirection: "row", gap: 10 }}>
        {running ? (
          <Button title="Durdur" variant="ghost" loading={busy} onPress={() => onAct(ad, "pause")} style={{ flex: 1, minHeight: 44 }} />
        ) : (
          <Button title="Yayına al" loading={busy} disabled={ad.status === "DISAPPROVED"} onPress={() => onAct(ad, "publish")} style={{ flex: 1, minHeight: 44 }} />
        )}
        <Button title="Meta'da aç" variant="ghost" onPress={() => Linking.openURL(adsManagerUrl(ad))} style={{ flex: 1, minHeight: 44 }} />
      </View>
    </Card>
  );
}

function Kpi({ label, value, note, main }: { label: string; value: string; note?: string; main?: boolean }) {
  return (
    <View style={[st.kpi, main && st.kpiMain]}>
      <T variant="small" style={{ color: colors.muted }} numberOfLines={1}>{label}</T>
      <T style={{ fontFamily: fonts.bodySemi, fontSize: main ? 20 : 16 }}>{value}</T>
      {note ? <T variant="small" style={{ color: colors.faint }}>{note}</T> : null}
    </View>
  );
}

const st = StyleSheet.create({
  body: { padding: 18, gap: 14, paddingBottom: 40 },
  titleRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.line },
  chipOn: { backgroundColor: colors.indigo, borderColor: colors.indigo },
  summary: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  kpis: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  kpi: { flexGrow: 1, flexBasis: "30%", minWidth: 96, backgroundColor: colors.surface2, borderRadius: radius.sm, padding: 10, gap: 2 },
  kpiMain: { flexBasis: "100%", borderWidth: 1, borderColor: colors.indigo },
  thumb: { width: 64, height: 64, borderRadius: radius.sm, backgroundColor: colors.surface2, overflow: "hidden", alignItems: "center", justifyContent: "center" },
  pill: { alignSelf: "flex-start", paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill },
});
