import Ionicons from "@expo/vector-icons/Ionicons";
import { Image } from "expo-image";
import { router } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, FlatList, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import AutoImage from "@/components/AutoImage";
import Markdown from "@/components/Markdown";
import MediaActions from "@/components/MediaActions";
import { T } from "@/components/ui";
import UpgradeCard from "@/components/UpgradeCard";
import VideoSuggestionCard from "@/components/VideoSuggestionCard";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import { colors, fonts, radius } from "@/lib/theme";
import { assetMeta, pickMedia, takePhoto, uploadUri, Uploaded } from "@/lib/upload";
import { FreeStatus, freeFooter, limitFromError, limitFromReply, LimitReason, VideoSuggestion, visibleLimit } from "@/lib/upgrade";

type Msg = {
  role: "user" | "assistant";
  content: string;
  attachments?: Uploaded[];
  images?: string[];
  imageError?: string | null;
  video?: VideoSuggestion | null;
};
type Summary = { id: string; title: string; updated_at: string };

const SUGGESTIONS = [
  "Kafem için bu hafta 3 Instagram gönderi fikri ver",
  "Mobilya mağazam için %40 indirim kampanya görseli hazırla",
  "Yeni ürünüm için kısa bir Reels kurgusu yaz",
];

export default function Chat() {
  const { usage, refresh } = useSession();
  const free = usage?.plan === "deneme";
  const [chatId, setChatId] = useState(() => `${Date.now()}`);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<Uploaded[]>([]);
  const [uploading, setUploading] = useState(false);
  const [imageMode, setImageMode] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const [history, setHistory] = useState<Summary[] | null>(null);
  const [limitReason, setLimitReason] = useState<LimitReason | null>(null);
  const [freeStatus, setFreeStatus] = useState<FreeStatus | null>(null);
  const listRef = useRef<FlatList<Msg>>(null);
  const limit = visibleLimit(limitReason, free, freeStatus);

  // Ücretsiz kullanıcının kalan mesaj/görsel hakkı (web ile aynı uç)
  useEffect(() => {
    if (!free) {
      setFreeStatus(null);
      return;
    }
    let alive = true;
    api<FreeStatus>("/api/free/status")
      .then((s) => alive && setFreeStatus(s))
      .catch(() => {
        // durum alınamazsa sohbet yine çalışır; hak dolunca 429 ile kart açılır
      });
    return () => {
      alive = false;
    };
  }, [free]);

  // Uygulama içi satın alma (RevenueCat) gelene kadar Hesap ekranındaki bilgiyle aynı mesaj
  const pickPlan = useCallback(() => {
    Alert.alert("Paketler", "Uygulama içi satın alma bir sonraki sürümde geliyor.");
  }, []);

  const save = useCallback(async (id: string, msgs: Msg[]) => {
    const title = (msgs.find((m) => m.role === "user")?.content || "Yeni sohbet").slice(0, 60);
    try {
      await api(`/api/chats/${encodeURIComponent(id)}`, { method: "PUT", body: { title, messages: msgs } });
    } catch {
      // kaydedilemezse sohbet yine ekranda kalır
    }
  }, []);

  const send = async (override?: string) => {
    const content = (override ?? text).trim();
    if ((!content && !files.length) || sending || uploading) return;
    if (limit === "chat") return; // mesaj hakkı doldu: paket kartı gösteriliyor
    setError("");
    setLimitReason(null);
    const user: Msg = { role: "user", content, attachments: files.length ? files : undefined };
    const next = [...messages, user];
    setMessages(next);
    setText("");
    setFiles([]);
    setSending(true);
    try {
      const data = await api<any>(free ? "/api/free/chat" : "/api/content/chat", {
        body: {
          messages: next.map((m) => ({ role: m.role, content: m.content, attachments: m.attachments ?? [] })),
          mode: imageMode ? "image" : "chat",
        },
      });
      const reply: Msg = { role: "assistant", content: data.reply || "", images: data.images ?? [], imageError: data.image_error, video: data.video };
      const all = [...next, reply];
      setMessages(all);
      setImageMode(false);
      if (data.free) setFreeStatus(data.free);
      setLimitReason(limitFromReply(data));
      save(chatId, all);
      refresh();
    } catch (e) {
      const reason = e instanceof ApiError ? limitFromError(e.status, free) : null;
      if (reason) {
        setLimitReason(reason);
        setFreeStatus((s) => (s ? { ...s, chat: { ...s.chat, remaining: 0 } } : s));
      } else {
        setError(e instanceof ApiError ? e.message : "Yanıt alınamadı, tekrar dene.");
      }
      setMessages(messages);
      setText(content);
      setFiles(user.attachments ?? []);
    } finally {
      setSending(false);
    }
  };

  const attach = async (source: "library" | "camera") => {
    setMenu(false);
    const assets = source === "camera" ? await takePhoto() : await pickMedia({ multiple: 4 });
    if (!assets.length) return;
    setUploading(true);
    try {
      const up = await Promise.all(assets.slice(0, 4).map((a) => { const m = assetMeta(a); return uploadUri(a.uri, m.name, m.type); }));
      setFiles((f) => [...f, ...up].slice(0, 4));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Fotoğraf yüklenemedi, tekrar dene.");
    } finally {
      setUploading(false);
    }
  };

  const newChat = () => {
    setChatId(`${Date.now()}`);
    setMessages([]);
    setError("");
    setLimitReason(null);
  };

  const openHistory = async () => {
    setHistory([]);
    try {
      setHistory(await api<Summary[]>("/api/chats?limit=60"));
    } catch {
      setHistory([]);
    }
  };

  const openChat = async (id: string) => {
    setHistory(null);
    try {
      const c = await api<{ id: string; messages: Msg[] }>(`/api/chats/${encodeURIComponent(id)}`);
      setChatId(c.id);
      setMessages(c.messages || []);
      setLimitReason(null);
    } catch {
      setError("Sohbet açılamadı.");
    }
  };

  const credits = usage?.credits.remaining ?? 0;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
      <View style={st.header}>
        <Pressable onPress={openHistory} hitSlop={10} accessibilityLabel="Geçmiş sohbetler">
          <Ionicons name="time-outline" size={24} color={colors.fg} />
        </Pressable>
        <Image source={require("@/assets/images/logo.png")} style={{ width: 92, height: 27 }} contentFit="contain" />
        <Pressable onPress={newChat} hitSlop={10} accessibilityLabel="Yeni sohbet">
          <Ionicons name="create-outline" size={24} color={colors.fg} />
        </Pressable>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={0}>
        {messages.length === 0 ? (
          limit ? (
            <ScrollView contentContainerStyle={{ padding: 16 }}>
              <UpgradeCard reason={limit} onPick={pickPlan} />
            </ScrollView>
          ) : (
          <View style={st.empty}>
            <T variant="h2" style={{ textAlign: "center" }}>Bugün ne üretelim?</T>
            <T variant="muted" style={{ textAlign: "center" }}>Fikrini yaz; gönderi, kampanya görseli ya da video kurgusu hazırlayalım.</T>
            <View style={{ gap: 10, width: "100%" }}>
              {SUGGESTIONS.map((s) => (
                <Pressable key={s} style={st.suggest} onPress={() => send(s)}>
                  <T variant="small" style={{ color: colors.fg }}>{s}</T>
                </Pressable>
              ))}
            </View>
          </View>
          )
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(_, i) => `${i}`}
            contentContainerStyle={{ padding: 16, gap: 18 }}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
            renderItem={({ item }) => <Bubble m={item} onVideoLocked={() => setLimitReason("video")} />}
            ListFooterComponent={
              sending ? (
                <View style={st.typing}><ActivityIndicator color={colors.indigoSoft} /><T variant="muted">{imageMode ? "Görsel hazırlanıyor…" : "Yazıyor…"}</T></View>
              ) : limit ? (
                <UpgradeCard reason={limit} onPick={pickPlan} />
              ) : undefined
            }
            keyboardDismissMode="interactive"
          />
        )}

        <View style={st.composerWrap}>
          {error ? <T variant="small" style={{ color: colors.danger, marginBottom: 6 }}>{error}</T> : null}
          {files.length > 0 || uploading ? (
            <View style={st.files}>
              {files.map((f, i) => (
                <View key={f.url}>
                  <Image source={{ uri: f.url }} style={st.thumb} />
                  <Pressable style={st.remove} onPress={() => setFiles((x) => x.filter((_, j) => j !== i))} hitSlop={8}>
                    <Ionicons name="close" size={12} color={colors.white} />
                  </Pressable>
                </View>
              ))}
              {uploading && <View style={[st.thumb, { alignItems: "center", justifyContent: "center" }]}><ActivityIndicator color={colors.fg} /></View>}
            </View>
          ) : null}
          {imageMode && (
            <Pressable onPress={() => setImageMode(false)} style={st.modeChip}>
              <Ionicons name="image" size={14} color={colors.indigoSoft} />
              <T variant="small" style={{ color: colors.indigoSoft }}>Görsel oluştur</T>
              <Ionicons name="close" size={14} color={colors.indigoSoft} />
            </Pressable>
          )}
          <View style={st.composer}>
            <Pressable onPress={() => setMenu(true)} style={st.plus} accessibilityLabel="Ekle">
              <Ionicons name="add" size={24} color={colors.fg} />
            </Pressable>
            <TextInput
              style={st.input}
              value={text}
              onChangeText={setText}
              placeholder={imageMode ? "Görselde ne olsun?" : "Mesajını yaz…"}
              placeholderTextColor={colors.faint}
              multiline
            />
            <Pressable onPress={() => send()} style={[st.send, ((!text.trim() && !files.length) || limit === "chat") && { opacity: 0.4 }]} disabled={sending || limit === "chat"} accessibilityLabel="Gönder">
              <Ionicons name="arrow-up" size={20} color={colors.white} />
            </Pressable>
          </View>
          <T variant="small" style={{ color: colors.faint, textAlign: "center", marginTop: 6 }}>
            {free ? freeFooter(freeStatus) : `${credits} kredin var`}
          </T>
        </View>
      </KeyboardAvoidingView>

      <Modal visible={menu} transparent animationType="fade" onRequestClose={() => setMenu(false)}>
        <Pressable style={st.scrim} onPress={() => setMenu(false)}>
          <View style={st.sheet}>
            <MenuRow icon="image-outline" title="Görsel oluştur" onPress={() => { setMenu(false); setImageMode(true); }} />
            <MenuRow icon="images-outline" title="Fotoğraf ekle" onPress={() => attach("library")} />
            <MenuRow icon="camera-outline" title="Fotoğraf çek" onPress={() => attach("camera")} />
            <MenuRow icon="videocam-outline" title="Video üret" onPress={() => { setMenu(false); router.push({ pathname: "/uret", params: { tab: "video" } }); }} />
            <MenuRow icon="megaphone-outline" title="Reklam ver" onPress={() => { setMenu(false); router.push("/reklam"); }} />
          </View>
        </Pressable>
      </Modal>

      <Modal visible={history !== null} animationType="slide" onRequestClose={() => setHistory(null)} presentationStyle="pageSheet">
        <View style={{ flex: 1, backgroundColor: colors.bg, padding: 20, gap: 12 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <T variant="h2">Sohbetler</T>
            <Pressable onPress={() => setHistory(null)} hitSlop={10}><Ionicons name="close" size={26} color={colors.fg} /></Pressable>
          </View>
          <FlatList
            data={history ?? []}
            keyExtractor={(c) => c.id}
            ListEmptyComponent={<T variant="muted">Henüz kayıtlı sohbet yok.</T>}
            renderItem={({ item }) => (
              <Pressable onPress={() => openChat(item.id)} style={st.histRow}>
                <T numberOfLines={1}>{item.title}</T>
              </Pressable>
            )}
          />
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function MenuRow({ icon, title, onPress }: { icon: keyof typeof Ionicons.glyphMap; title: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={st.menuRow}>
      <Ionicons name={icon} size={22} color={colors.fg} />
      <T>{title}</T>
    </Pressable>
  );
}

function Bubble({ m, onVideoLocked }: { m: Msg; onVideoLocked: () => void }) {
  if (m.role === "user") {
    return (
      <View style={{ alignItems: "flex-end", gap: 6 }}>
        {m.attachments?.length ? (
          <View style={{ flexDirection: "row", gap: 6 }}>
            {m.attachments.map((a) => <Image key={a.url} source={{ uri: a.url }} style={{ width: 72, height: 72, borderRadius: 10 }} />)}
          </View>
        ) : null}
        {m.content ? <View style={st.userBubble}><T>{m.content}</T></View> : null}
      </View>
    );
  }
  return (
    <View style={{ gap: 10 }}>
      {m.content ? <Markdown text={m.content} /> : null}
      {m.images?.map((u) => (
        <View key={u} style={{ gap: 8 }}>
          <AutoImage uri={u} />
          <MediaActions url={u} />
        </View>
      ))}
      {m.imageError ? <T variant="small" style={{ color: colors.danger }}>{m.imageError}</T> : null}
      {m.video ? <VideoSuggestionCard video={m.video} onLocked={onVideoLocked} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 18, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.line },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24, gap: 14 },
  suggest: { padding: 14, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  typing: { flexDirection: "row", gap: 10, alignItems: "center" },
  composerWrap: { paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, borderTopWidth: 1, borderTopColor: colors.line, backgroundColor: colors.bg },
  composer: { flexDirection: "row", alignItems: "flex-end", gap: 8, backgroundColor: colors.surface, borderRadius: 24, borderWidth: 1, borderColor: colors.line, padding: 6 },
  plus: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface2 },
  input: { flex: 1, color: colors.fg, fontFamily: fonts.body, fontSize: 16, maxHeight: 140, paddingVertical: 8, paddingHorizontal: 4 },
  send: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: colors.indigo },
  files: { flexDirection: "row", gap: 8, marginBottom: 8 },
  thumb: { width: 56, height: 56, borderRadius: 10, backgroundColor: colors.surface2 },
  remove: { position: "absolute", top: -6, right: -6, width: 20, height: 20, borderRadius: 10, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.line, alignItems: "center", justifyContent: "center" },
  modeChip: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, backgroundColor: "#1D1C4A", marginBottom: 8 },
  scrim: { flex: 1, backgroundColor: "rgba(0,0,0,0.55)", justifyContent: "flex-end" },
  sheet: { backgroundColor: colors.surface, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 12, paddingBottom: 34, borderWidth: 1, borderColor: colors.line },
  menuRow: { flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 15, paddingHorizontal: 10 },
  histRow: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.line },
  userBubble: { backgroundColor: colors.surface2, borderRadius: 18, borderBottomRightRadius: 6, paddingHorizontal: 14, paddingVertical: 10, maxWidth: "85%" },
});
