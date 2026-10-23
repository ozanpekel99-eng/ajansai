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
import { CreditLine, EmptyResult, NoCreditsNotice, WorkspaceProps, useRevealOnMobile } from "./common";
import { LibraryGrid } from "./Library";

const RATIOS = [
  { value: "ASPECT_4_5", label: "Gönderi 4:5" },
  { value: "ASPECT_1_1", label: "Kare 1:1" },
  { value: "ASPECT_9_16", label: "Hikâye 9:16" },
  { value: "ASPECT_16_9", label: "Yatay 16:9" },
];

// Her üretim/revizyon bir sürüm; revize her zaman seçili sürümün üzerine yapılır.
type Version = { url: string; concept: string; prompt: string; note: string; ratio: string };
type ImageResponse = { image_url: string | null; error: string | null; prompt?: string; note?: string };

const REVISE_EXAMPLES = ["Yazıyı daha büyük ve dikkat çekici yap", "Arka planı daha sıcak tonlara çevir", "Sağ alta \"Son 3 gün\" rozeti ekle"];

/** Ne yazacağını bilmeyenler için doldurulacak hazır kalıplar */
const TEMPLATES = [
  { label: "Kampanya / indirim", text: "Ürün: \nSatış fiyatı: \nKampanya fiyatı: \nTaksit: \nSon gün: \nMağaza adı: " },
  { label: "Yeni ürün", text: "Yeni ürünümüz: \nÖne çıkan özelliği: \nFiyatı: \nMağaza adı: " },
  { label: "Özel gün", text: "Özel gün: \nMesaj: \nVarsa indirim: \nMağaza adı: " },
  { label: "Duyuru", text: "Duyuru: \nTarih / saat: \nMağaza adı: " },
];

export default function GorselWorkspace({ tab, showCreate }: WorkspaceProps) {
  const params = useSearchParams();
  const { usage, refresh, openCheckout } = useSession();
  const freePlan = usage?.plan === "deneme";
  const [concept, setConcept] = useState(params.get("konsept") || "");
  const [ratio, setRatio] = useState("ASPECT_4_5");
  const [refs, setRefs] = useState<PendingFile[]>([]);
  const uploader = useUploader(["image"], 4, refs.length, (f) => setRefs((x) => [...x, f]));
  const [versions, setVersions] = useState<Version[]>([]);
  const [current, setCurrent] = useState(0);
  const [revision, setRevision] = useState("");
  const [loading, setLoading] = useState<false | "new" | "revise">(false);
  const [error, setError] = useState("");
  const resultRef = useRevealOnMobile<HTMLElement>(loading === "new");
  const result = versions[current] || null;

  const cost = usage?.costs.image ?? 4;
  const locked = !!usage && (freePlan || usage.credits.remaining < cost);

  const run = async (body: object, kind: "new" | "revise", concept: string, r: string) => {
    setLoading(kind);
    setError("");
    try {
      const data = await api<ImageResponse>("/api/content/image", { method: "POST", body: JSON.stringify(body) });
      if (!data.image_url) {
        setError(data.error || "Görsel üretilemedi, kredin iade edildi.");
        return false;
      }
      const v: Version = { url: data.image_url, concept, prompt: data.prompt || concept, note: data.note || "", ratio: r };
      setVersions((list) => {
        const next = kind === "new" ? [v] : [...list, v];
        setCurrent(next.length - 1);
        return next;
      });
      return true;
    } catch (err) {
      setError((err as ApiError).message);
      return false;
    } finally {
      setLoading(false);
      refresh();
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run({ concept, aspect_ratio: ratio, reference_urls: refs.map((f) => f.url) }, "new", concept, ratio);
  };

  // Seçili sürüm düzenlenir: model görseli bozmadan yalnızca isteneni değiştirir.
  const revise = async (e: FormEvent) => {
    e.preventDefault();
    if (!result || !revision.trim()) return;
    const ok = await run(
      {
        concept: revision,
        aspect_ratio: result.ratio,
        base_url: result.url,
        previous_prompt: result.prompt,
        reference_urls: refs.map((f) => f.url),
      },
      "revise",
      revision,
      result.ratio,
    );
    if (ok) setRevision("");
  };

  if (tab === "history") {
    return (
      <LibraryGrid
        kind="image"
        onOpen={(item) => {
          setVersions([{ url: item.url, concept: item.prompt, prompt: item.prompt, note: "", ratio }]);
          setCurrent(0);
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
          <Link href="/">sohbette</Link> &quot;görsel üret&quot; diyerek ayda 3 görsel üretebilirsin.
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
          <label>1. Ürün fotoğrafın (önerilir)</label>
          {uploader.field}
          <FileChips files={refs} onRemove={(id) => setRefs((x) => x.filter((f) => f.id !== id))} />
          <UploadProgress busy={uploader.busy} />
          {refs.length < 4 && (
            <button type="button" className="add-file" onClick={uploader.pick} disabled={uploader.busy.length > 0}>
              <Icon name="plus" size={16} /> Ürün fotoğrafı ekle
            </button>
          )}
          <span className="hint">
            Ürününün fotoğrafını eklersen görselde aynı ürün, aynı haliyle kullanılır. En iyi sonuç için ürünün net, önden
            çekilmiş fotoğrafını yükle (en fazla 4). Ek kredi harcamaz.
          </span>
          {uploader.error && <small className="error-text">{uploader.error}</small>}
        </div>
        <div className="field">
          <label htmlFor="g-concept">2. Görselde ne olsun?</label>
          <div className="chip-row template-chips">
            {TEMPLATES.map((t) => (
              <button key={t.label} type="button" className="chip" onClick={() => setConcept(t.text)}>
                {t.label}
              </button>
            ))}
          </div>
          <textarea
            id="g-concept"
            required
            rows={5}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="Örn: Buzdolabı + çamaşır makinesi kampanyası. Satış fiyatı 69.600₺, nakit 46.350₺, taksitli 50.500₺. En üstte mağaza adım: Başak Arçelik. Son gün 31 Ekim."
          />
          <span className="hint">
            Fiyatları, tarihleri ve mağaza adını yazman yeterli; tasarımı biz yaparız. Yazdığın fiyat, tarih ve isimler görsele
            aynen yazılır. Beğenmediğin yeri sağdaki &quot;Revize et&quot; ile söyle.
          </span>
          <SampleToConcept target="image" onConcept={setConcept} />
        </div>
        <div className="chip-row">
          <ChipSelect icon="ratio" label="Format" value={ratio} onChange={setRatio} options={RATIOS.map((r) => ({ value: r.value, label: r.label }))} />
        </div>
        <div className="generate">
          <button className="btn btn-primary btn-block" type="submit" disabled={!!loading || locked}>
            {loading === "new" ? "Görsel üretiliyor…" : versions.length ? `Yeni görsel üret · ${cost} kredi` : `Görsel üret · ${cost} kredi`}
          </button>
          <CreditLine cost={cost} />
        </div>
      </form>

      <section ref={resultRef} className="panel ws-panel result-area" aria-live="polite">
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
        {loading === "new" ? (
          <EmptyResult loading text="Görsel üretiliyor, genelde 20–40 saniye sürer." />
        ) : result ? (
          <>
            <div className={`media-result ${loading === "revise" ? "is-busy" : ""}`}>
              <img src={result.url} alt={result.concept} />
              {loading === "revise" && <span className="media-busy">Revize ediliyor…</span>}
            </div>
            {result.note && <p className="revise-note">{result.note}</p>}
            {versions.length > 1 && (
              <div className="version-strip" aria-label="Sürümler">
                {versions.map((v, i) => (
                  <button
                    key={v.url}
                    type="button"
                    className={i === current ? "active" : ""}
                    onClick={() => setCurrent(i)}
                    title={i === 0 ? "İlk görsel" : v.concept}
                  >
                    <img src={v.url} alt="" />
                    <span>{i === 0 ? "İlk" : `Revize ${i}`}</span>
                  </button>
                ))}
              </div>
            )}
            <form className="revise-box field" onSubmit={revise}>
              <label htmlFor="g-revise">Revize et</label>
              <div className="inline-row">
                <input
                  id="g-revise"
                  value={revision}
                  onChange={(e) => setRevision(e.target.value)}
                  placeholder="Neyi değiştirelim? Örn. yazıyı daha büyük ve dikkat çekici yap"
                  disabled={!!loading}
                />
                <button className="btn btn-primary btn-sm" type="submit" disabled={!!loading || locked || !revision.trim()}>
                  {loading === "revise" ? "Revize ediliyor…" : `Revize et · ${cost} kredi`}
                </button>
              </div>
              <div className="chip-row">
                {REVISE_EXAMPLES.map((x) => (
                  <button key={x} type="button" className="chip chip-soft" onClick={() => setRevision(x)} disabled={!!loading}>
                    {x}
                  </button>
                ))}
              </div>
              <span className="hint">
                {versions.length > 1 && current !== versions.length - 1
                  ? "Seçili sürümün üzerine revize edilir."
                  : "Görsel sıfırdan üretilmez; yalnızca istediğin değişiklik yapılır."}
              </span>
            </form>
          </>
        ) : (
          <EmptyResult text="Konseptini yaz ve formatı seç, görsel burada görünecek." />
        )}
      </section>
    </div>
    </>
  );
}
