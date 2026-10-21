"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError, api } from "../../lib/api";
import { HistoryEntry, addHistory, readHistory } from "../../lib/history";
import { useSession } from "../../lib/session";
import { videoCredits } from "../../lib/plans";
import { CreditLine, EmptyResult, HistoryList, LockedNotice, NoCreditsNotice, WorkspaceProps } from "./common";

type Result = { url: string; concept: string };

export default function VideoWorkspace({ tab, showCreate }: WorkspaceProps) {
  const params = useSearchParams();
  const { usage, refresh } = useSession();
  const [concept, setConcept] = useState(params.get("konsept") || "");
  const [imageUrl, setImageUrl] = useState(params.get("gorsel") || "");
  const [duration, setDuration] = useState(5);
  const [status, setStatus] = useState<"idle" | "starting" | "running">("idle");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<HistoryEntry<Result>[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setHistory(readHistory<Result>("video"));
    return () => clearTimeout(timer.current);
  }, []);

  const cost = videoCredits(duration, usage?.costs);
  const featureLocked = !!usage && !usage.video_enabled;
  const locked = featureLocked || (!!usage && usage.credits.remaining < cost);

  const poll = (jobId: string, text: string) => {
    const check = async () => {
      try {
        const data = await api<{ status: string; video_url: string | null }>(`/api/content/video/${jobId}`);
        if (data.status === "SUCCEEDED" && data.video_url) {
          const r = { url: data.video_url, concept: text };
          setResult(r);
          setStatus("idle");
          addHistory("video", text.slice(0, 80), r);
          setHistory(readHistory("video"));
          return;
        }
        if (data.status === "FAILED") {
          setError("Video üretilemedi, kredin iade edildi. Konsepti sadeleştirip tekrar dene.");
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
        body: JSON.stringify({ concept, duration, image_url: imageUrl || null }),
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

  return (
    <div className="workspace">
      <form className="panel ws-panel" onSubmit={submit}>
        <h2>Video ayarları</h2>
        {featureLocked ? <LockedNotice text="Video üretimi Başlangıç ve üzeri paketlerde açılır." /> : <NoCreditsNotice cost={cost} />}
        <div className="field">
          <label htmlFor="v-concept">Konsept</label>
          <textarea
            id="v-concept"
            required
            rows={5}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="Buzdolabı kapağı yavaşça açılıyor, içerideki ışık yanıyor, kamera içeri doğru ilerliyor"
          />
          <span className="hint">Hareketi ve kamera açısını anlat. Video dikey (9:16) üretilir.</span>
        </div>
        <div className="field">
          <label htmlFor="v-image">Başlangıç görseli (isteğe bağlı)</label>
          <input id="v-image" type="url" value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="Görsel aracından gelen bağlantı" />
          <span className="hint">Bir görsel verirsen video o görsel canlandırılarak üretilir.</span>
        </div>
        <div className="field">
          <label>Süre</label>
          <div className="segmented">
            {[5, 10].map((d) => (
              <button type="button" key={d} className={duration === d ? "active" : ""} onClick={() => setDuration(d)} aria-pressed={duration === d}>
                {d} saniye · {videoCredits(d, usage?.costs)} kredi
              </button>
            ))}
          </div>
        </div>
        <div className="generate">
          <button className="btn btn-primary btn-block" type="submit" disabled={busy || locked}>
            {status === "starting" ? "Başlatılıyor…" : status === "running" ? "Video üretiliyor…" : `Video üret · ${cost} kredi`}
          </button>
          {!featureLocked && <CreditLine cost={cost} />}
        </div>
      </form>

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>
          Sonuç
          {result && (
            <a className="btn btn-ghost btn-sm" href={result.url} target="_blank" rel="noreferrer">
              İndir
            </a>
          )}
        </h2>
        {error && <div className="notice error">{error}</div>}
        {busy ? (
          <EmptyResult loading text="Video üretiliyor. Bu genelde 1–3 dakika sürer; sayfadan ayrılma." />
        ) : result ? (
          <div className="media-result">
            <video src={result.url} controls playsInline />
          </div>
        ) : (
          <EmptyResult text="Konseptini yaz, dikey video burada görünecek." />
        )}
      </section>
    </div>
  );
}
