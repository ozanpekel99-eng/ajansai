import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { api } from "../api";
import { WEB_URL } from "../config";

const FIELDS = [
  { key: "business_name", label: "İşletme adı", placeholder: "Cafe Lorem" },
  { key: "sector", label: "Sektör", placeholder: "Kafe / Restoran" },
  {
    key: "target_audience",
    label: "Hedef kitle",
    placeholder: "25-40 yaş, şehirde yaşayan profesyoneller",
  },
  { key: "tone", label: "Marka tonu", placeholder: "Samimi ve eğlenceli" },
  {
    key: "topic",
    label: "Bu içerik ne hakkında olmalı?",
    placeholder: "Yeni sezon soğuk kahve menümüz",
    multiline: true,
  },
];

export default function IdeasScreen({ onLogout }) {
  const [form, setForm] = useState({
    business_name: "",
    sector: "",
    target_audience: "",
    tone: "",
    topic: "",
  });
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [videoState, setVideoState] = useState({});
  const [usage, setUsage] = useState(null);

  const refreshUsage = () =>
    api("/api/plans/usage")
      .then(setUsage)
      .catch(() => {});

  useEffect(() => {
    refreshUsage();
  }, []);

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const pollVideo = (jobId, index) => {
    const check = async () => {
      try {
        const data = await api(`/api/content/video/${jobId}`);

        if (data.status === "SUCCEEDED") {
          setVideoState((prev) => ({ ...prev, [index]: { status: "hazır", url: data.video_url } }));
        } else if (data.status === "FAILED") {
          setVideoState((prev) => ({ ...prev, [index]: { status: "başarısız, kota iade edildi" } }));
          refreshUsage();
        } else {
          setVideoState((prev) => ({ ...prev, [index]: { status: "üretiliyor" } }));
          setTimeout(check, 4000);
        }
      } catch {
        setTimeout(check, 8000);
      }
    };
    check();
  };

  const handleVideoRequest = async (idea, index) => {
    setVideoState((prev) => ({ ...prev, [index]: { status: "başlatılıyor" } }));
    try {
      const data = await api("/api/content/video", {
        method: "POST",
        body: JSON.stringify({ concept: idea.concept }),
      });

      if (data.error || !data.job_id) {
        setVideoState((prev) => ({
          ...prev,
          [index]: { status: "hata: " + (data.error || "bilinmeyen") },
        }));
        return;
      }
      pollVideo(data.job_id, index);
    } catch (e) {
      setVideoState((prev) => ({ ...prev, [index]: { status: e.message } }));
    } finally {
      refreshUsage();
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    setIdeas([]);
    try {
      const data = await api("/api/content/ideas", {
        method: "POST",
        body: JSON.stringify({ ...form, idea_count: 4 }),
      });
      if (data.error) {
        setError("Fikirler oluşturulurken bir sorun oluştu.");
      } else {
        setIdeas(data.ideas || []);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      refreshUsage();
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.brand}>ajans<Text style={styles.brandAccent}>AI</Text></Text>
      <Text style={styles.title}>İşletmenin içeriğini ve reklamını tek yerden yönet.</Text>

      <View style={styles.topRow}>
        {usage ? (
          <Text style={styles.usage}>
            {usage.plan === "deneme"
              ? `Deneme · ${Math.max((usage.ideas.quota || 0) - usage.ideas.used, 0)} fikir kaldı`
              : `${usage.plan_name} · ${usage.video.quota - usage.video.used} video kaldı`}
          </Text>
        ) : (
          <View />
        )}
        <View style={{ flexDirection: "row" }}>
          <TouchableOpacity onPress={() => Linking.openURL(`${WEB_URL}/pricing`)}>
            <Text style={styles.topLink}>Paketler</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={onLogout}>
            <Text style={[styles.topLink, styles.muted]}>Çıkış</Text>
          </TouchableOpacity>
        </View>
      </View>

      {FIELDS.map((field) => (
        <View style={styles.field} key={field.key}>
          <Text style={styles.label}>{field.label}</Text>
          <TextInput
            style={[styles.input, field.multiline && styles.textarea]}
            placeholder={field.placeholder}
            placeholderTextColor="rgba(255,255,255,0.4)"
            value={form[field.key]}
            onChangeText={(v) => update(field.key, v)}
            multiline={field.multiline}
          />
        </View>
      ))}

      <TouchableOpacity style={styles.button} onPress={handleSubmit} disabled={loading}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Fikir üret</Text>
        )}
      </TouchableOpacity>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {ideas.map((idea, i) => (
        <View style={styles.card} key={i}>
          <Text style={styles.platform}>
            {idea.platform} · {idea.format}
          </Text>
          <Text style={styles.cardTitle}>{idea.title}</Text>
          <Text style={styles.cardText}>{idea.concept}</Text>
          <Text style={styles.caption}>"{idea.caption}"</Text>
          <Text style={styles.hashtags}>{idea.hashtags?.join("  ")}</Text>

          <View style={styles.videoRow}>
            {!videoState[i] && (
              <TouchableOpacity style={styles.ghostButton} onPress={() => handleVideoRequest(idea, i)}>
                <Text style={styles.ghostButtonText}>Video oluştur</Text>
              </TouchableOpacity>
            )}
            {videoState[i] && videoState[i].status === "hazır" ? (
              <TouchableOpacity onPress={() => Linking.openURL(videoState[i].url)}>
                <Text style={styles.videoLink}>Videoyu izle →</Text>
              </TouchableOpacity>
            ) : (
              videoState[i] && <Text style={styles.videoStatus}>{videoState[i].status}…</Text>
            )}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f7" },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  usage: { fontSize: 12, color: "rgba(10,10,10,0.6)", backgroundColor: "rgba(65,63,245,0.12)", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  topLink: { fontWeight: "600", color: "#0a0a0a", marginLeft: 16 },
  muted: { color: "rgba(10,10,10,0.5)", fontWeight: "400" },
  content: { padding: 20, paddingTop: 60, paddingBottom: 60 },
  brand: { fontSize: 20, fontWeight: "700", color: "#0a0a0a" },
  brandAccent: { color: "#413ff5" },
  title: { fontSize: 26, fontWeight: "700", color: "#0a0a0a", marginTop: 8, marginBottom: 24 },
  field: { marginBottom: 14 },
  label: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    color: "rgba(10,10,10,0.5)",
    marginBottom: 6,
  },
  input: {
    backgroundColor: "#0a0a0a",
    color: "#f5f5f7",
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  textarea: { minHeight: 70, textAlignVertical: "top" },
  button: {
    backgroundColor: "#413ff5",
    borderRadius: 999,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  buttonText: { fontWeight: "700", color: "#fff" },
  error: { color: "#d64545", marginTop: 12, fontSize: 13 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 6,
    padding: 16,
    marginTop: 16,
    borderWidth: 1,
    borderColor: "rgba(10,10,10,0.1)",
  },
  platform: { fontSize: 11, color: "rgba(10,10,10,0.5)", marginBottom: 4 },
  cardTitle: { fontSize: 16, fontWeight: "700", marginBottom: 6 },
  cardText: { fontSize: 13, color: "rgba(10,10,10,0.75)", marginBottom: 10 },
  caption: {
    fontSize: 13,
    fontStyle: "italic",
    backgroundColor: "#f5f5f7",
    borderRadius: 4,
    padding: 10,
    marginBottom: 8,
  },
  hashtags: { fontSize: 12, color: "#413ff5" },
  videoRow: {
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "rgba(10,10,10,0.1)",
    borderStyle: "dashed",
    flexDirection: "row",
    alignItems: "center",
  },
  ghostButton: {
    borderWidth: 1,
    borderColor: "#0a0a0a",
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  ghostButtonText: { fontSize: 12.5, fontWeight: "700", color: "#0a0a0a" },
  videoStatus: { fontSize: 12.5, color: "rgba(10,10,10,0.5)" },
  videoLink: { fontSize: 12.5, fontWeight: "700", color: "#413ff5" },
});
