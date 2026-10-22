"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ApiError, api } from "../../lib/api";
import { StockPhoto, useFreeStatus } from "../../lib/free";
import { HistoryEntry, addHistory, readHistory } from "../../lib/history";
import { useSession } from "../../lib/session";
import { FileChips, PendingFile, UploadProgress, useUploader } from "../Attachments";
import { ChipSelect, SampleToConcept } from "../Controls";
import { FreeImagePanel, StockLibrary } from "../FreeTools";
import Icon from "../Icon";
import { CreditLine, EmptyResult, HistoryList, LockedNotice, NoCreditsNotice, WorkspaceProps } from "./common";

const RATIOS = [
  { value: "ASPECT_1_1", label: "Kare 1:1" },
  { value: "ASPECT_9_16", label: "Hikâye 9:16" },
  { value: "ASPECT_3_4", label: "Gönderi 3:4" },
  { value: "ASPECT_16_9", label: "Yatay 16:9" },
];

type Result = { url: string; concept: string };
type Mode = "pro" | "ucretsiz" | "stok";

const MODES: { value: Mode; label: string }[] = [
  { value: "pro", label: "Seedream · 4 kredi" },
  { value: "ucretsiz", label: "Ücretsiz AI" },
  { value: "stok", label: "Stok fotoğraf" },
];

export default function GorselWorkspace({ tab, showCreate }: WorkspaceProps) {
  const params = useSearchParams();
  const { usage, refresh, openCheckout } = useSession();
  const free = useFreeStatus();
  const freePlan = usage?.plan === "deneme";
  const [mode, setMode] = useState<Mode | null>((params.get("mod") as Mode) || null);
  const [concept, setConcept] = useState(params.get("konsept") || "");
  const [ratio, setRatio] = useState("ASPECT_1_1");
  const [refs, setRefs] = useState<PendingFile[]>([]);
  const uploader = useUploader(["image"], 4, refs.length, (f) => setRefs((x) => [...x, f]));
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<HistoryEntry<Result>[]>([]);

  useEffect(() => setHistory(readHistory<Result>("gorsel")), []);
  useEffect(() => {
    if (usage && mode === null) setMode(usage.plan === "deneme" ? "ucretsiz" : "pro");
  }, [usage, mode]);

  const cost = usage?.costs.image ?? 4;
  const locked = !!usage && (usage.plan === "deneme" || usage.credits.remaining < cost);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ image_url: string | null; error: string | null }>("/api/content/image", {
        method: "POST",
        body: JSON.stringify({ concept, aspect_ratio: ratio, reference_urls: refs.map((f) => f.url) }),
      });
      if (!data.image_url) {
        setError(data.error || "Görsel üretilemedi, kredin iade edildi.");
      } else {
        const r = { url: data.image_url, concept };
        setResult(r);
        addHistory("gorsel", concept.slice(0, 80), r);
        setHistory(readHistory("gorsel"));
      }
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
      refresh();
    }
  };

  if (tab === "history") {
    return <HistoryList items={history} onOpen={(item) => {
          setResult(item.data);
          setMode("pro");
          showCreate();
        }} />;
  }

  const remember = (url: string, title: string) => {
    addHistory("gorsel", title.slice(0, 80), { url, concept: title });
    setHistory(readHistory("gorsel"));
  };

  const toVideo = (url: string, text: string) => (
    <Link className="btn btn-ghost btn-sm" href={`/araclar/video?konsept=${encodeURIComponent(text)}&gorsel=${encodeURIComponent(url)}`}>
      Videoya çevir
    </Link>
  );

  const modeRow = (
    <div className="mode-row">
      <div className="tabs" role="tablist" aria-label="Görsel kaynağı">
        {MODES.map((m) => (
          <button key={m.value} type="button" role="tab" aria-selected={mode === m.value} className={mode === m.value ? "active" : ""} onClick={() => setMode(m.value)}>
            {m.label}
          </button>
        ))}
      </div>
      <span className="hint">
        {mode === "pro"
          ? "En yüksek kalite; ürün fotoğrafını örnek alabilir."
          : mode === "ucretsiz"
            ? free.status
              ? `Kredi harcamaz · 30 günde ${free.status.images.limit} görsel, ${free.status.images.remaining} hakkın var.`
              : "Kredi harcamaz."
            : "Telifsiz fotoğraflar, sınırsız ve ücretsiz."}
      </span>
    </div>
  );

  if (mode === null) return null;

  if (mode === "ucretsiz") {
    return (
      <>
        {modeRow}
        <FreeImagePanel
          status={free.status}
          onStatus={free.setStatus}
          initialConcept={concept}
          onCreated={(url, text) => url.startsWith("https://") && remember(url, text)}
          resultActions={(url, text) => (usage?.video_enabled && url.startsWith("https://") ? toVideo(url, text) : null)}
          upsell={
            <button type="button" className="btn btn-light btn-sm" onClick={() => openCheckout("baslangic")}>
              Paket seç
            </button>
          }
        />
      </>
    );
  }

  if (mode === "stok") {
    return (
      <>
        {modeRow}
        <StockLibrary
          enabled={free.status ? free.status.stock_enabled : true}
          onSave={async (photo: StockPhoto) => {
            const data = await api<{ url: string }>("/api/free/stock/save", {
              method: "POST",
              body: JSON.stringify({ photo_id: photo.id }),
            });
            remember(data.url, photo.alt || `Stok fotoğraf · ${photo.photographer}`);
            return data.url;
          }}
          saveLabel="Görsellerime ekle"
          savedActions={(url, photo) => (
            <>
              <span className="chip">Görsellerine eklendi</span>
              {usage?.video_enabled && toVideo(url, photo.alt || "")}
            </>
          )}
        />
      </>
    );
  }

  return (
    <>
    {modeRow}
    {freePlan && (
      <LockedNotice text="Seedream ile yüksek kaliteli üretim ücretli paketlerde (görsel başı 4 kredi). Ücretsiz AI ve stok fotoğrafları kullanmaya devam edebilirsin." />
    )}
    <div className="workspace">
      <form className="panel ws-panel" onSubmit={submit}>
        <h2>Girdi</h2>
        {!freePlan && <NoCreditsNotice cost={cost} />}
        <div className="field">
          <label htmlFor="g-concept">Konsept</label>
          <textarea
            id="g-concept"
            required
            rows={5}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="Beyaz mutfakta yeni nesil gri buzdolabı, sabah ışığı, ön planda taze meyveler"
          />
          <span className="hint">Ne görünmesini istediğini, ışığı ve ortamı yaz. Yazı içeren görsellerde metni tırnak içinde ver.</span>
          <SampleToConcept target="image" onConcept={setConcept} />
        </div>
        <div className="field">
          <label>Örnek görseller (isteğe bağlı)</label>
          {uploader.field}
          <FileChips files={refs} onRemove={(id) => setRefs((x) => x.filter((f) => f.id !== id))} />
          <UploadProgress busy={uploader.busy} />
          {refs.length < 4 && (
            <button type="button" className="add-file" onClick={uploader.pick} disabled={uploader.busy.length > 0}>
              <Icon name="plus" size={16} /> Ürün veya stil görseli ekle
            </button>
          )}
          <span className="hint">
            En fazla 4 görsel. Kendi ürününü yüklersen yeni görselde aynı ürün kullanılır; stil örneği yüklersen o tarzda üretilir. Ek kredi harcamaz.
          </span>
          {uploader.error && <small className="error-text">{uploader.error}</small>}
        </div>
        <div className="chip-row">
          <ChipSelect icon="ratio" label="Format" value={ratio} onChange={setRatio} options={RATIOS.map((r) => ({ value: r.value, label: r.label }))} />
        </div>
        <div className="generate">
          <button className="btn btn-primary btn-block" type="submit" disabled={loading || locked}>
            {loading ? "Görsel üretiliyor…" : `Görsel üret · ${cost} kredi`}
          </button>
          <CreditLine cost={cost} />
        </div>
      </form>

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>
          Sonuç
          {result && (
            <span style={{ display: "flex", gap: 6 }}>
              <a className="btn btn-ghost btn-sm" href={result.url} target="_blank" rel="noreferrer">
                İndir
              </a>
              <Link
                className="btn btn-ghost btn-sm"
                href={`/araclar/video?konsept=${encodeURIComponent(result.concept)}&gorsel=${encodeURIComponent(result.url)}`}
              >
                Videoya çevir
              </Link>
            </span>
          )}
        </h2>
        {error && <div className="notice error">{error}</div>}
        {loading ? (
          <EmptyResult loading text="Görsel üretiliyor, genelde 10–30 saniye sürer." />
        ) : result ? (
          <div className="media-result">
            <img src={result.url} alt={result.concept} />
          </div>
        ) : (
          <EmptyResult text="Konseptini yaz ve formatı seç, görsel burada görünecek." />
        )}
      </section>
    </div>
    </>
  );
}
