import Ionicons from "@expo/vector-icons/Ionicons";
import { Image } from "expo-image";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Modal, Pressable, RefreshControl, StyleSheet, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import AutoImage from "@/components/AutoImage";
import MediaActions from "@/components/MediaActions";
import Player from "@/components/Player";
import { T } from "@/components/ui";
import { api } from "@/lib/api";
import { colors, fonts } from "@/lib/theme";

type Item = { id: string; kind: "image" | "video"; url: string; prompt: string; created_at: string };
type Filter = "all" | "image" | "video";

export default function Kutuphane() {
  const [filter, setFilter] = useState<Filter>("all");
  const [items, setItems] = useState<Item[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<Item | null>(null);
  const { width } = useWindowDimensions();
  const size = (width - 18 * 2 - 8 * 2) / 3;

  const load = useCallback(async (f: Filter) => {
    setLoading(true);
    try {
      const q = f === "all" ? "" : `kind=${f}&`;
      const d = await api<{ items: Item[] }>(`/api/content/library?${q}limit=120`);
      setItems(d.items);
    } catch {
      setItems((x) => x ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load(filter);
    }, [filter, load]),
  );

  const remove = (it: Item) =>
    Alert.alert("Silinsin mi?", "Bu içerik kütüphanenden kaldırılacak.", [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Sil",
        style: "destructive",
        onPress: async () => {
          try {
            await api(`/api/content/library/${it.id}`, { method: "DELETE" });
          } catch {
            // 204 gövdesiz döner; hata olsa da listeyi yenileriz
          }
          setOpen(null);
          load(filter);
        },
      },
    ]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
      <View style={st.top}>
        <T variant="h2">Kütüphane</T>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {(["all", "image", "video"] as Filter[]).map((f) => (
            <Pressable key={f} onPress={() => setFilter(f)} style={[st.chip, filter === f && st.chipOn]}>
              <T variant="small" style={{ color: filter === f ? colors.white : colors.muted, fontFamily: fonts.bodyMedium }}>{f === "all" ? "Tümü" : f === "image" ? "Görseller" : "Videolar"}</T>
            </Pressable>
          ))}
        </View>
      </View>
      {items === null ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.indigoSoft} />
      ) : (
        <FlatList
          data={items}
          numColumns={3}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: 18, gap: 8 }}
          columnWrapperStyle={{ gap: 8 }}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={() => load(filter)} tintColor={colors.fg} />}
          ListEmptyComponent={
            <View style={{ alignItems: "center", gap: 8, marginTop: 60 }}>
              <Ionicons name="images-outline" size={40} color={colors.faint} />
              <T variant="muted" style={{ textAlign: "center" }}>Ürettiğin görsel ve videolar burada birikir.</T>
            </View>
          }
          renderItem={({ item }) => (
            <Pressable onPress={() => setOpen(item)} style={{ width: size, height: size * 1.4, borderRadius: 10, overflow: "hidden", backgroundColor: colors.surface }}>
              {item.kind === "image" ? (
                <Image source={{ uri: item.url }} style={{ flex: 1 }} contentFit="cover" />
              ) : (
                <View style={[st.center, { flex: 1 }]}>
                  <Ionicons name="play-circle" size={36} color={colors.fg} />
                  <T variant="small" numberOfLines={2} style={{ color: colors.muted, textAlign: "center", paddingHorizontal: 6 }}>{item.prompt}</T>
                </View>
              )}
            </Pressable>
          )}
        />
      )}

      <Modal visible={!!open} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setOpen(null)}>
        {open && (
          <View style={{ flex: 1, backgroundColor: colors.bg, padding: 18, gap: 14 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Pressable onPress={() => remove(open)} hitSlop={10}><Ionicons name="trash-outline" size={22} color={colors.danger} /></Pressable>
              <Pressable onPress={() => setOpen(null)} hitSlop={10}><Ionicons name="close" size={26} color={colors.fg} /></Pressable>
            </View>
            {open.kind === "image" ? <AutoImage uri={open.url} /> : <Player url={open.url} />}
            <MediaActions url={open.url} />
            {open.prompt ? <T variant="muted" numberOfLines={4}>{open.prompt}</T> : null}
          </View>
        )}
      </Modal>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  top: { paddingHorizontal: 18, paddingTop: 8, paddingBottom: 12, gap: 12, borderBottomWidth: 1, borderBottomColor: colors.line },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 999, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  chipOn: { backgroundColor: colors.indigo, borderColor: colors.indigo },
  center: { alignItems: "center", justifyContent: "center", gap: 6 },
});
