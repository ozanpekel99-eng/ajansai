"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";

import Header from "./components/Header";
import { ApiError, api } from "./lib/api";
import { useAuth } from "./lib/useAuth";

type Idea = {
  platform: string;
  format: string;
  title: string;
  concept: string;
  caption: string;
  hashtags: string[];
};

export default function Home() {
  const { ready, usage, refreshUsage } = useAuth();
  const [form, setForm] = useState({
    business_name: "",
    sector: "",
    target_audience: "",
    tone: "",
    topic: "",
  });
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [needsPlan, setNeedsPlan] = useState(false);
  const [videoState, setVideoState] = useState<Record<number, { status: string; url?: string }>>({});

  const update = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const setVideo = (index: number, value: { status: string; url?: string }) =>
    setVideoState((prev) => ({ ...prev, [index]: value }));

  const pollVideo = (jobId: string, index: number) => {
    const check = async () => {
      try {
        const data = await api(`/api/content/video/${jobId}`);
        if (data.status === "SUCCEEDED") {
          setVideo(index, { status: "hazır", url: data.video_url });
        } else if (data.status === "FAILED") {
          setVideo(index, { status: "başarısız oldu, kotan iade edildi" });
          refreshUsage();
        } else {
          setVideo(index, { status: "üretiliyor" });
          setTimeout(check, 4000);
        }
      } catch {
        setTimeout(check, 8000);
      }
    };
    check();
  };

  const handleVideoRequest = async (idea: Idea, index: number) => {
    setVideo(index, { status: "başlatılıyor" });
    try {
      const data = await api("/api/content/video", {
        method: "POST",
        body: JSON.stringify({ concept: idea.concept }),
      });
      if (data.error || !data.job_id) {
        setVideo(index, { status: data.error || "video başlatılamadı" });
        return;
      }
      pollVideo(data.job_id, index);
    } catch (err: any) {
      setVideo(index, { status: err.message });
    } finally {
      refreshUsage();
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setNeedsPlan(false);
    setIdeas([]);

    try {
      const data = await api("/api/content/ideas", {
        method: "POST",
        body: JSON.stringify({ ...form, idea_count: 4 }),
      });
      if (data.error) {
        setError("Fikirler oluşturulurken bir sorun oluştu, tekrar dener misin?");
      } else {
        setIdeas(data.ideas || []);
      }
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.message);
      setNeedsPlan(apiErr.status === 402);
    } finally {
      setLoading(false);
      refreshUsage();
    }
  };

  if (!ready) return null;

  return (
    <div className="page">
      <Header usage={usage} />

      <section className="hero">
        <h1>İşletmenin içeriğini ve reklamını tek yerden yönet.</h1>
        <p>
          Ürününü ve hedef kitleni anlat, sana platforma özel içerik fikirleri,
          hazır caption'lar ve reklam önerileri çıkaralım.
        </p>
      </section>

      {needsPlan && (
        <div className="notice">
          {error} <Link href="/pricing">Paketleri gör →</Link>
        </div>
      )}

      <form className="form-card" onSubmit={handleSubmit}>
        <div className="field">
          <label>İşletme adı</label>
          <input required value={form.business_name} onChange={(e) => update("business_name", e.target.value)} placeholder="Cafe Lorem" />
        </div>

        <div className="field">
          <label>Sektör</label>
          <input required value={form.sector} onChange={(e) => update("sector", e.target.value)} placeholder="Kafe / Restoran" />
        </div>

        <div className="field">
          <label>Hedef kitle</label>
          <input
            required
            value={form.target_audience}
            onChange={(e) => update("target_audience", e.target.value)}
            placeholder="25-40 yaş, şehirde yaşayan profesyoneller"
          />
        </div>

        <div className="field">
          <label>Marka tonu</label>
          <input required value={form.tone} onChange={(e) => update("tone", e.target.value)} placeholder="Samimi ve eğlenceli" />
        </div>

        <div className="field full">
          <label>Bu içerik ne hakkında olmalı?</label>
          <textarea
            required
            rows={3}
            value={form.topic}
            onChange={(e) => update("topic", e.target.value)}
            placeholder="Yeni sezon soğuk kahve menümüzü tanıtmak istiyoruz"
          />
        </div>

        <div className="submit-row">
          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Üretiliyor…" : "Fikir üret"}
          </button>
          {error && !needsPlan && <span className="error-text">{error}</span>}
        </div>
      </form>

      {ideas.length > 0 && (
        <section className="results">
          <h2>{ideas.length} içerik fikri hazır</h2>
          <div className="vitrin">
            {ideas.map((idea, i) => (
              <div className="idea-card" key={i}>
                <span className="tab">{idea.format}</span>
                <div className="platform">{idea.platform}</div>
                <h3>{idea.title}</h3>
                <p>{idea.concept}</p>
                <div className="caption">"{idea.caption}"</div>
                <div className="hashtags">
                  {idea.hashtags?.map((tag, j) => (
                    <span key={j}>{tag}</span>
                  ))}
                </div>

                <div className="video-row">
                  {!videoState[i] && (
                    <button className="ghost" onClick={() => handleVideoRequest(idea, i)}>
                      Video oluştur
                    </button>
                  )}
                  {videoState[i] && videoState[i].status === "hazır" ? (
                    <a className="video-link" href={videoState[i].url} target="_blank" rel="noreferrer">
                      Videoyu izle →
                    </a>
                  ) : (
                    videoState[i] && <span className="video-status">{videoState[i].status}…</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
