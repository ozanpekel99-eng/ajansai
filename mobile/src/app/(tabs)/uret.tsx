import Ionicons from "@expo/vector-icons/Ionicons";
import { Image } from "expo-image";
import { router, useLocalSearchParams } from "expo-router";
import { ComponentRef, useEffect, useRef, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import AutoImage from "@/components/AutoImage";
import MediaActions from "@/components/MediaActions";
import Player from "@/components/Player";
import { Button, Card, ErrorText, Input, T } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import { colors, fonts, radius } from "@/lib/theme";
import { assetMeta, pickMedia, takePhoto, uploadUri } from "@/lib/upload";

type Tab = "gorsel" | "video";

export default function Uret() {
  const params = useLocalSearchParams<{ tab?: string; konsept?: string; gorsel?: string }>();
  const [tab, setTab] = useState<Tab>(params.tab === "video" ? "video" : "gorsel");
  useEffect(() => {
    if (params.tab === "video" || params.tab === "gorsel") setTab(params.tab as Tab);
  }, [params.tab]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
      <View style={st.top}>
        <T variant="h2">Üret</T>
        <View style={st.seg}>
          {(["gorsel", "video"] as Tab[]).map((t) => (
            <Pressable key={t} onPress={() => setTab(t)} style={[st.segBtn, tab === t && st.segOn]} accessibilityRole="tab" accessibilityState={{ selected: tab === t }}>
              <Ionicons name={t === "gorsel" ? "image-outline" : "videocam-outline"} size={16} color={tab === t ? colors.fg : colors.muted} />
              <T style={[st.segText, tab === t && { color: colors.fg }]}>{t === "gorsel" ? "Görsel" : "Video"}</T>
            </Pressable>
          ))}
        </View>
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        {tab === "gorsel" ? <ImageTool /> : <VideoTool initialConcept={params.konsept} initialImage={params.gorsel} />}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function PhotoPicker({ photos, setPhotos, max, label }: { photos: string[]; setPhotos: (p: string[]) => void; max: number; label: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const add = async (source: "library" | "camera") => {
    setError("");
    const assets = source === "camera" ? await takePhoto() : await pickMedia({ multiple: max - photos.length });
    if (!assets.length) return;
    setBusy(true);
    try {
      const up = await Promise.all(assets.slice(0, max - photos.length).map((a) => { const m = assetMeta(a); return uploadUri(a.uri, m.name, m.type); }));
      setPhotos([...photos, ...up.map((u) => u.url)].slice(0, max));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Fotoğraf yüklenemedi, tekrar dene.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <View style={{ gap: 8 }}>
      <T variant="label">{label}</T>
      <View style={{ flexDirection: "row", gap: 10, flexWrap: "wrap" }}>
        {photos.map((u, i) => (
          <View key={u}>
            <Image source={{ uri: u }} style={st.photo} />
            <Pressable style={st.remove} onPress={() => setPhotos(photos.filter((_, j) => j !== i))} hitSlop={8} accessibilityLabel="Fotoğrafı kaldır">
              <Ionicons name="close" size={13} color={colors.white} />
            </Pressable>
          </View>
        ))}
        {busy && <View style={[st.photo, st.center]}><ActivityIndicator color={colors.fg} /></View>}
        {photos.length < max && !busy && (
          <>
            <Pressable style={[st.photo, st.center, st.addBox]} onPress={() => add("library")} accessibilityLabel="Galeriden ekle">
              <Ionicons name="images-outline" size={22} color={colors.muted} />
              <T variant="small" style={{ color: colors.muted }}>Galeri</T>
            </Pressable>
            <Pressable style={[st.photo, st.center, st.addBox]} onPress={() => add("camera")} accessibilityLabel="Fotoğraf çek">
              <Ionicons name="camera-outline" size={22} color={colors.muted} />
              <T variant="small" style={{ color: colors.muted }}>Kamera</T>
            </Pressable>
          </>
        )}
      </View>
      <ErrorText>{error}</ErrorText>
    </View>
  );
}

function Chips<V extends string>({ value, options, onChange }: { value: V; options: { v: V; label: string }[]; onChange: (v: V) => void }) {
  return (
    <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
      {options.map((o) => (
        <Pressable key={o.v} onPress={() => onChange(o.v)} style={[st.chip, value === o.v && st.chipOn]} accessibilityRole="radio" accessibilityState={{ selected: value === o.v }}>
          <T variant="small" style={{ color: value === o.v ? colors.white : colors.muted, fontFamily: fonts.bodyMedium }}>{o.label}</T>
        </Pressable>
      ))}
    </View>
  );
}

const ASPECTS = [
  { v: "ASPECT_4_5", label: "Gönderi 4:5" },
  { v: "ASPECT_1_1", label: "Kare 1:1" },
  { v: "ASPECT_9_16", label: "Hikaye 9:16" },
  { v: "ASPECT_16_9", label: "Yatay 16:9" },
] as const;
type Aspect = (typeof ASPECTS)[number]["v"];

function ImageTool() {
  const { usage, refresh } = useSession();
  const free = usage?.plan === "deneme";
  const [photos, setPhotos] = useState<string[]>([]);
  const [concept, setConcept] = useState("");
  const [aspect, setAspect] = useState<Aspect>("ASPECT_4_5");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ url: string; prompt: string } | null>(null);
  const [revision, setRevision] = useState("");
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);

  const generate = async (revise?: string) => {
    const text = (revise ?? concept).trim();
    if (text.length < 3) {
      setError("Görselde ne olmasını istediğini yaz.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      if (free) {
        const d = await api<{ image_url: string | null; error: string | null }>("/api/free/image", { body: { concept: text, reference_urls: photos.slice(0, 2) } });
        if (!d.image_url) throw new ApiError(500, d.error || "Görsel üretilemedi.");
        setResult({ url: d.image_url, prompt: "" });
      } else {
        const body: Record<string, unknown> = { concept: text, aspect_ratio: aspect, reference_urls: photos };
        if (revise && result) {
          body.base_url = result.url;
          body.previous_prompt = result.prompt;
        }
        const d = await api<{ image_url: string | null; error: string | null; prompt: string }>("/api/content/image", { body });
        if (!d.image_url) throw new ApiError(500, d.error || "Görsel üretilemedi, kredin iade edildi.");
        setResult({ url: d.image_url, prompt: d.prompt });
        setRevision("");
      }
      refresh();
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 300);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Görsel üretilemedi, tekrar dene.");
    } finally {
      setBusy(false);
    }
  };

  const cost = usage?.costs?.image ?? 5;
  return (
    <ScrollView ref={scroll} contentContainerStyle={st.body} keyboardShouldPersistTaps="handled">
      <PhotoPicker photos={photos} setPhotos={setPhotos} max={free ? 2 : 4} label="Ürün fotoğrafın (önerilir)" />
      <Input label="Görselde ne olsun?" value={concept} onChangeText={setConcept} multiline style={{ minHeight: 96, paddingTop: 12, textAlignVertical: "top" }} placeholder="Örn: Tüm ürünlerde %40 indirim, ücretsiz teslimat ve montaj" />
      {!free && (
        <View style={{ gap: 8 }}>
          <T variant="label">Boyut</T>
          <Chips value={aspect} options={[...ASPECTS]} onChange={setAspect} />
        </View>
      )}
      <ErrorText>{error}</ErrorText>
      <Button title={busy ? "Görsel hazırlanıyor…" : free ? "Görsel üret" : `Görsel üret · ${cost} kredi`} onPress={() => generate()} loading={busy} />
      {busy && <T variant="muted" style={{ textAlign: "center" }}>Kampanya görselleri 30-60 saniye sürebilir.</T>}

      {result && (
        <Card style={{ gap: 12 }}>
          <AutoImage uri={result.url} />
          <MediaActions url={result.url} />
          {!free && (
            <View style={{ gap: 8 }}>
              <Input value={revision} onChangeText={setRevision} placeholder="Değiştirmek istediğini yaz (örn: arka planı beyaz yap)" />
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Button title="Düzenle" variant="ghost" style={{ flex: 1 }} onPress={() => generate(revision)} disabled={!revision.trim() || busy} />
                <Button
                  title="Videoya çevir"
                  variant="ghost"
                  style={{ flex: 1 }}
                  onPress={() => router.setParams({ tab: "video", gorsel: result.url, konsept: "" })}
                />
              </View>
            </View>
          )}
        </Card>
      )}
    </ScrollView>
  );
}

type Job = { id: string; status: "PENDING" | "SUCCEEDED" | "FAILED"; url?: string | null; error?: string | null };

function VideoTool({ initialConcept, initialImage }: { initialConcept?: string; initialImage?: string }) {
  const { usage, refresh } = useSession();
  const [photos, setPhotos] = useState<string[]>(initialImage ? [initialImage] : []);
  const [concept, setConcept] = useState(initialConcept ?? "");
  const [duration, setDuration] = useState<"4" | "6" | "8">("6");
  const [resolution, setResolution] = useState<"720p" | "1080p">("1080p");
  const [aspect, setAspect] = useState<"9:16" | "16:9">("9:16");
  const [audio, setAudio] = useState<"0" | "1">("0");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (initialImage) setPhotos([initialImage]);
    if (initialConcept) setConcept(initialConcept);
  }, [initialImage, initialConcept]);

  useEffect(() => {
    if (!job || job.status !== "PENDING") return;
    const t = setInterval(async () => {
      try {
        const d = await api<{ status: Job["status"]; video_url: string | null; error: string | null }>(`/api/content/video/${job.id}`);
        if (d.status !== "PENDING") {
          setJob({ id: job.id, status: d.status, url: d.video_url, error: d.error });
          refresh();
        }
      } catch {
        // geçici ağ hatası: bir sonraki turda tekrar sorulur
      }
    }, 6000);
    return () => clearInterval(t);
  }, [job, refresh]);

  if (usage && !usage.video_enabled) {
    return (
      <View style={[st.body, { flex: 1, justifyContent: "center" }]}>
        <Card style={{ gap: 12 }}>
          <T variant="h3">Video üretimi paketlerle açılır</T>
          <T variant="muted">Başlangıç paketinden itibaren ürün fotoğrafından reklam videosu üretebilirsin.</T>
          <Button title="Paketleri gör" onPress={() => router.push("/hesap")} />
        </Card>
      </View>
    );
  }

  const costTable = usage?.costs?.[audio === "1" ? "video_audio" : "video"]?.[resolution];
  const cost = costTable?.[duration];

  const start = async () => {
    if (concept.trim().length < 3) {
      setError("Videoda ne olmasını istediğini yaz.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const d = await api<{ job_id: string | null; error: string | null }>("/api/content/video", {
        body: {
          concept: concept.trim(),
          reference_urls: photos,
          duration: Number(duration),
          resolution,
          aspect_ratio: aspect,
          audio: audio === "1",
        },
      });
      if (!d.job_id) throw new ApiError(500, d.error || "Video başlatılamadı, kredin iade edildi.");
      setJob({ id: d.job_id, status: "PENDING" });
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Video başlatılamadı, tekrar dene.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={st.body} keyboardShouldPersistTaps="handled">
      <PhotoPicker photos={photos} setPhotos={setPhotos} max={4} label="Ürün fotoğrafı ya da görsel (önerilir)" />
      <Input label="Videoda ne olsun?" value={concept} onChangeText={setConcept} multiline style={{ minHeight: 96, paddingTop: 12, textAlignVertical: "top" }} placeholder="Örn: Bu kampanya görselinden Instagram reklam videosu yap" />
      <View style={{ gap: 8 }}>
        <T variant="label">Süre</T>
        <Chips value={duration} options={[{ v: "4", label: "4 sn" }, { v: "6", label: "6 sn" }, { v: "8", label: "8 sn" }]} onChange={setDuration} />
      </View>
      <View style={{ gap: 8 }}>
        <T variant="label">Kalite ve yön</T>
        <Chips value={resolution} options={[{ v: "1080p", label: "1080p" }, { v: "720p", label: "720p" }]} onChange={setResolution} />
        <Chips value={aspect} options={[{ v: "9:16", label: "Dikey (Reels)" }, { v: "16:9", label: "Yatay" }]} onChange={setAspect} />
        <Chips value={audio} options={[{ v: "0", label: "Sessiz" }, { v: "1", label: "Sesli" }]} onChange={setAudio} />
      </View>
      <ErrorText>{error}</ErrorText>
      <Button title={cost ? `Video üret · ${cost} kredi` : "Video üret"} onPress={start} loading={busy} disabled={job?.status === "PENDING"} />

      {job && (
        <Card style={{ gap: 12 }}>
          {job.status === "PENDING" && (
            <View style={{ alignItems: "center", gap: 10, paddingVertical: 24 }}>
              <ActivityIndicator color={colors.indigoSoft} size="large" />
              <T variant="h3">Videon hazırlanıyor</T>
              <T variant="muted" style={{ textAlign: "center" }}>Genelde 1-3 dakika sürer. Bu ekrandan çıkabilirsin; video Kütüphane'ye de düşer.</T>
            </View>
          )}
          {job.status === "SUCCEEDED" && job.url && (
            <>
              <Player url={job.url} vertical={aspect === "9:16"} />
              <MediaActions url={job.url} />
            </>
          )}
          {job.status === "FAILED" && <T style={{ color: colors.danger }}>{job.error || "Video üretilemedi, kredin iade edildi."}</T>}
        </Card>
      )}
    </ScrollView>
  );
}

const st = StyleSheet.create({
  top: { paddingHorizontal: 18, paddingTop: 8, paddingBottom: 12, gap: 12, borderBottomWidth: 1, borderBottomColor: colors.line },
  seg: { flexDirection: "row", backgroundColor: colors.surface, borderRadius: 12, padding: 4, borderWidth: 1, borderColor: colors.line },
  segBtn: { flex: 1, flexDirection: "row", gap: 6, paddingVertical: 9, borderRadius: 9, alignItems: "center", justifyContent: "center" },
  segOn: { backgroundColor: colors.surface2 },
  segText: { fontFamily: fonts.bodyMedium, color: colors.muted },
  body: { padding: 18, gap: 18, paddingBottom: 40 },
  photo: { width: 76, height: 76, borderRadius: 12, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center", gap: 2 },
  addBox: { borderWidth: 1, borderStyle: "dashed", borderColor: colors.line },
  remove: { position: "absolute", top: -6, right: -6, width: 22, height: 22, borderRadius: 11, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.line, alignItems: "center", justifyContent: "center" },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  chipOn: { backgroundColor: colors.indigo, borderColor: colors.indigo },
});
