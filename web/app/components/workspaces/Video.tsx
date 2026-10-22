"use client";

import { downloadHref, onDownload } from "../../lib/download";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError, VideoDuration, VideoResolution, api } from "../../lib/api";
import { HistoryEntry, addHistory, readHistory } from "../../lib/history";
import { DEFAULT_COSTS, VIDEO_DURATIONS, VIDEO_RESOLUTIONS, num, videoCredits } from "../../lib/plans";
import { useSession } from "../../lib/session";
import { PendingFile, UploadProgress, useUploader } from "../Attachments";
import { ChipSelect, SampleToConcept, Toggle } from "../Controls";
import Icon from "../Icon";
import { CreditLine, EmptyResult, LockedNotice, NoCreditsNotice, WorkspaceProps } from "./common";
import { LibraryGrid } from "./Library";

type Result = { url: string; concept: string };
type Ratio = "9:16" | "16:9" | "1:1";

const RATIOS: { value: Ratio; label: string; note: string }[] = [
  { value: "9:16", label: "9:16", note: "Reels, hikâye" },
  { value: "1:1", label: "1:1", note: "Akış gönderisi" },
  { value: "16:9", label: "16:9", note: "YouTube, ekran" },
];

export default function VideoWorkspace({ tab, showCreate }: WorkspaceProps) {
  const params = useSearchParams();
  const { usage, refresh } = useSession();
  const [concept, setConcept] = useState(params.get("konsept") || "");
  const [images, setImages] = useState<PendingFile[]>(() => {
    const g = params.get("gorsel");
    return g ? [{ id: "sohbet", url: g, content_type: "image/jpeg", name: "Sohbetteki görsel", kind: "image" }] : [];
  });
  const uploader = useUploader(["image"], 4, images.length, (f) => setImages((x) => [...x, f]));
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
  const composeCost = images.length > 1 ? costs.image : 0;
  const cost = videoCredits(duration, resolution, costs, audio) + composeCost;
  const featureLocked = !!usage && !usage.video_enabled;
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
          reference_urls: images.map((f) => f.url),
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
      <LibraryGrid
        kind="video"
        onOpen={(item) => {
          setResult({ url: item.url, concept: item.prompt });
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

        <div className="field">
          <label>Görseller (isteğe bağlı)</label>
          {uploader.field}
          <div className="thumb-grid">
            {images.map((f) => (
              <figure key={f.id}>
                <img src={f.url} alt={f.name} />
                <button type="button" aria-label={`${f.name} kaldır`} onClick={() => setImages((x) => x.filter((y) => y.id !== f.id))}>
                  <Icon name="close" size={12} />
                </button>
              </figure>
            ))}
            {images.length < 4 && (
              <button type="button" className="thumb-add" onClick={uploader.pick} disabled={uploader.busy.length > 0}>
                <Icon name="image" size={18} />
                <span>{images.length ? "Görsel ekle" : "Görsel yükle"}</span>
              </button>
            )}
          </div>
          <UploadProgress busy={uploader.busy} />
          <span className="hint">
            {images.length > 1
              ? `Görseller tek sahnede birleştirilip videonun açılış karesi yapılır (+${costs.image} kredi).`
              : "En fazla 4 görsel, aynı anda birden fazla seçebilirsin. Tek görselde video o görselden başlar; birden fazlasında ürün, kişi ve mekân tek sahnede birleştirilir."}
          </span>
          {uploader.error && <small className="error-text">{uploader.error}</small>}
        </div>

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
          <button className="btn btn-primary btn-block" type="submit" disabled={busy || locked || uploader.busy.length > 0}>
            {status === "starting" ? "Başlatılıyor…" : status === "running" ? "Video üretiliyor…" : `Video üret · ${num(cost)} kredi`}
          </button>
          {!featureLocked && <CreditLine cost={cost} />}
        </div>
      </form>

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>
          Sonuç
          {result && (
            <a className="btn btn-ghost btn-sm" href={downloadHref(result.url)} download onClick={onDownload(result.url)}>
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
            {perSecond("4k")} kredi. Tek görsel ek kredi harcamaz; birden fazla görsel birleştirilirse +{costs.image} kredi. Üretim başarısız olursa kredi iade edilir.
          </p>
        </div>
      </section>
    </div>
  );
}
