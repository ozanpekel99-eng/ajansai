"use client";

import { downloadHref } from "../../lib/download";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError, VideoDuration, VideoResolution, api } from "../../lib/api";
import { HistoryEntry, addHistory, readHistory } from "../../lib/history";
import { DEFAULT_COSTS, VIDEO_DURATIONS, VIDEO_RESOLUTIONS, num, videoCredits } from "../../lib/plans";
import { useSession } from "../../lib/session";
import { ChipSelect, ImageSlot, SampleToConcept, Toggle } from "../Controls";
import { CreditLine, EmptyResult, HistoryList, LockedNotice, NoCreditsNotice, WorkspaceProps } from "./common";

type Result = { url: string; concept: string };
type Mode = "text" | "image";
type Ratio = "9:16" | "16:9" | "1:1";

const RATIOS: { value: Ratio; label: string; note: string }[] = [
  { value: "9:16", label: "9:16", note: "Reels, hikâye" },
  { value: "1:1", label: "1:1", note: "Akış gönderisi" },
  { value: "16:9", label: "16:9", note: "YouTube, ekran" },
];

export default function VideoWorkspace({ tab, showCreate }: WorkspaceProps) {
  const params = useSearchParams();
  const { usage, refresh } = useSession();
  const [mode, setMode] = useState<Mode>(params.get("gorsel") ? "image" : "text");
  const [concept, setConcept] = useState(params.get("konsept") || "");
  const [startFrame, setStartFrame] = useState(params.get("gorsel") || "");
  const [endFrame, setEndFrame] = useState("");
  const [duration, setDuration] = useState<VideoDuration>(5);
  const [resolution, setResolution] = useState<VideoResolution>("720p");
  const [ratio, setRatio] = useState<Ratio>("9:16");
  const [audio, setAudio] = useState(false);
  const [status, setStatus] = useState<"idle" | "starting" | "running">("idle");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<HistoryEntry<Result>[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setHistory(readHistory<Result>("video"));
    return () => clearTimeout(timer.current);
  }, []);

  const costs = usage?.costs ?? DEFAULT_COSTS;
  const cost = videoCredits(duration, resolution, costs, audio);
  const featureLocked = !!usage && !usage.video_enabled;
  const needsFrame = mode === "image" && !startFrame;
  const locked = featureLocked || (!!usage && usage.credits.remaining < cost);

  const poll = (jobId: string, text: string) => {
    const check = async () => {
      try {
        const data = await api<{ status: string; video_url: string | null; error: string | null }>(`/api/content/video/${jobId}`);
        if (data.status === "SUCCEEDED" && data.video_url) {
          const r = { url: data.video_url, concept: text };
          setResult(r);
          setStatus("idle");
          addHistory("video", text.slice(0, 80), r);
          setHistory(readHistory("video"));
          refresh();
          return;
        }
        if (data.status === "FAILED") {
          setError(data.error || "Video üretilemedi, kredin iade edildi. Konsepti sadeleştirip tekrar dene.");
          setStatus("idle");
          refresh();
          return;
        }
      } catch {
        // geçici hata: biraz bekleyip tekrar sor
      }
      timer.current = setTimeout(check, 5000);
    };
    check();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (needsFrame) {
      setError("Görselden video için bir başlangıç karesi yükle.");
      return;
    }
    setStatus("starting");
    setError("");
    setResult(null);
    try {
      const data = await api<{ job_id: string | null; error: string | null }>("/api/content/video", {
        method: "POST",
        body: JSON.stringify({
          concept,
          duration,
          resolution,
          aspect_ratio: ratio,
          audio,
          image_url: mode === "image" ? startFrame || null : null,
          end_image_url: mode === "image" ? endFrame || null : null,
        }),
      });
      if (!data.job_id) {
        setError(data.error || "Video başlatılamadı, kredin iade edildi.");
        setStatus("idle");
      } else {
        setStatus("running");
        poll(data.job_id, concept);
      }
    } catch (err) {
      setError((err as ApiError).message);
      setStatus("idle");
    } finally {
      refresh();
    }
  };

  if (tab === "history") {
    return (
      <HistoryList
        items={history}
        onOpen={(item) => {
          setResult(item.data);
          showCreate();
        }}
      />
    );
  }

  const busy = status !== "idle";
  const perSecond = (r: VideoResolution) =>
    (costs[audio ? "video_audio" : "video"][r]["5"] / 5).toLocaleString("tr-TR", { maximumFractionDigits: 1 });

  return (
    <div className="workspace">
      <form className="panel ws-panel" onSubmit={submit}>
        <div className="ws-title">
          <h2>Girdi</h2>
          <div className="segmented small" role="tablist" aria-label="Video türü">
            <button type="button" role="tab" aria-selected={mode === "text"} className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}>
              Metinden
            </button>
            <button type="button" role="tab" aria-selected={mode === "image"} className={mode === "image" ? "active" : ""} onClick={() => setMode("image")}>
              Görselden
            </button>
          </div>
        </div>
        {featureLocked ? <LockedNotice text="Video üretimi Başlangıç ve üzeri paketlerde açılır." /> : <NoCreditsNotice cost={cost} />}

        <div className="field">
          <label htmlFor="v-concept">Konsept</label>
          <textarea
            id="v-concept"
            required
            rows={4}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="Buzdolabı kapağı yavaşça açılıyor, içerideki ışık yanıyor, kamera içeri doğru ilerliyor"
          />
          <SampleToConcept target="video" onConcept={setConcept} />
        </div>

        {mode === "image" && (
          <div className="field">
            <label>Başlangıç ve bitiş karesi</label>
            <div className="slots">
              <ImageSlot label="Başlangıç karesi" required url={startFrame} onChange={setStartFrame} />
              <ImageSlot label="Bitiş karesi" url={endFrame} onChange={setEndFrame} />
            </div>
            <span className="hint">Video başlangıç karesindeki görselden başlar; bitiş karesi verirsen ona doğru ilerler.</span>
          </div>
        )}

        <Toggle
          label="Ses üret"
          note={resolution === "4k" ? "4K'da ek ücret yok" : "720p ve 1080p'de krediyi ikiye katlar"}
          checked={audio}
          onChange={setAudio}
        />

        <div className="chip-row">
          <ChipSelect
            icon="clock"
            label="Süre"
            value={duration}
            onChange={setDuration}
            options={VIDEO_DURATIONS.map((d) => ({ value: d, label: `${d} sn`, note: `${videoCredits(d, resolution, costs, audio)} kredi` }))}
          />
          <ChipSelect
            icon="tag"
            label="Çözünürlük"
            value={resolution}
            onChange={setResolution}
            options={VIDEO_RESOLUTIONS.map((r) => ({ value: r.value, label: r.label, note: `${videoCredits(duration, r.value, costs, audio)} kredi` }))}
          />
          <ChipSelect icon="ratio" label="Oran" value={ratio} onChange={setRatio} options={RATIOS} />
        </div>

        <div className="generate">
          <button className="btn btn-primary btn-block" type="submit" disabled={busy || locked || needsFrame}>
            {status === "starting" ? "Başlatılıyor…" : status === "running" ? "Video üretiliyor…" : `Video üret · ${num(cost)} kredi`}
          </button>
          {!featureLocked && <CreditLine cost={cost} />}
        </div>
      </form>

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>
          Sonuç
          {result && (
            <a className="btn btn-ghost btn-sm" href={downloadHref(result.url)} download>
              İndir
            </a>
          )}
        </h2>
        {error && <div className="notice error">{error}</div>}
        {busy ? (
          <EmptyResult
            loading
            text={
              resolution === "4k"
                ? "4K video üretiliyor. Bu 3–6 dakika sürebilir; sayfadan ayrılma."
                : "Video üretiliyor. Bu genelde 1–3 dakika sürer; sayfadan ayrılma."
            }
          />
        ) : result ? (
          <div className="media-result">
            <video src={result.url} controls playsInline />
          </div>
        ) : (
          <EmptyResult text="Konseptini yaz ya da bir görsel yükle; video burada görünecek." />
        )}
        <div className="price-note">
          <strong>Fiyat</strong>
          <p>
            Kredi = süre × çözünürlük{audio ? " (sesli)" : ""}. Saniye başına: 720p {perSecond("720p")}, 1080p {perSecond("1080p")}, 4K{" "}
            {perSecond("4k")} kredi. Üretim başarısız olursa kredi iade edilir; başlangıç ve bitiş karesi ek kredi harcamaz.
          </p>
        </div>
      </section>
    </div>
  );
}
