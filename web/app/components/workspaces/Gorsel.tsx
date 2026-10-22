"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ApiError, api } from "../../lib/api";
import { onDownload } from "../../lib/download";
import { useSession } from "../../lib/session";
import { FileChips, PendingFile, UploadProgress, useUploader } from "../Attachments";
import { ChipSelect, SampleToConcept } from "../Controls";
import Icon from "../Icon";
import { CreditLine, EmptyResult, NoCreditsNotice, WorkspaceProps } from "./common";
import { LibraryGrid } from "./Library";

const RATIOS = [
  { value: "ASPECT_1_1", label: "Kare 1:1" },
  { value: "ASPECT_9_16", label: "Hikâye 9:16" },
  { value: "ASPECT_3_4", label: "Gönderi 3:4" },
  { value: "ASPECT_16_9", label: "Yatay 16:9" },
];

type Result = { url: string; concept: string };

export default function GorselWorkspace({ tab, showCreate }: WorkspaceProps) {
  const params = useSearchParams();
  const { usage, refresh, openCheckout } = useSession();
  const freePlan = usage?.plan === "deneme";
  const [concept, setConcept] = useState(params.get("konsept") || "");
  const [ratio, setRatio] = useState("ASPECT_1_1");
  const [refs, setRefs] = useState<PendingFile[]>([]);
  const uploader = useUploader(["image"], 4, refs.length, (f) => setRefs((x) => [...x, f]));
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const cost = usage?.costs.image ?? 4;
  const locked = !!usage && (freePlan || usage.credits.remaining < cost);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ image_url: string | null; error: string | null }>("/api/content/image", {
        method: "POST",
        body: JSON.stringify({ concept, aspect_ratio: ratio, reference_urls: refs.map((f) => f.url) }),
      });
      if (!data.image_url) setError(data.error || "Görsel üretilemedi, kredin iade edildi.");
      else setResult({ url: data.image_url, concept });
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
      refresh();
    }
  };

  if (tab === "history") {
    return (
      <LibraryGrid
        kind="image"
        onOpen={(item) => {
          setResult({ url: item.url, concept: item.prompt });
          showCreate();
        }}
      />
    );
  }

  return (
    <>
    {freePlan && (
      <div className="notice">
        <span>
          Görsel aracı ücretli paketlerde (görsel başı {cost} kredi). Ücretsiz pakette{" "}
          <Link href="/">sohbette</Link> &quot;görsel üret&quot; diyerek ayda 6 görsel üretebilirsin.
        </span>
        <button type="button" className="btn btn-light btn-sm" onClick={() => openCheckout("baslangic")}>
          Paket seç
        </button>
      </div>
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
              <a className="btn btn-ghost btn-sm" href={result.url} download onClick={onDownload(result.url)}>
                <Icon name="download" size={14} /> İndir
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
