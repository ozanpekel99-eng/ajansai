"use client";

import { FormEvent, ReactNode, useState } from "react";

import { ApiError, api } from "../lib/api";
import { FreeStatus, StockPhoto, StockResult, downloadUrl } from "../lib/free";
import Icon from "./Icon";

/* ---------------- Ücretsiz AI görseli ---------------- */

export function FreeImagePanel({
  status,
  onStatus,
  initialConcept = "",
  onCreated,
  resultActions,
  upsell,
}: {
  status: FreeStatus | null;
  onStatus: (s: FreeStatus) => void;
  initialConcept?: string;
  onCreated?: (url: string, concept: string) => void;
  resultActions?: (url: string, concept: string) => ReactNode;
  upsell?: ReactNode;
}) {
  const [concept, setConcept] = useState(initialConcept);
  const [result, setResult] = useState<{ url: string; concept: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const left = status?.images.remaining;
  const enabled = status ? status.ai_image_enabled : true;
  const blocked = !enabled || left === 0;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ image_url: string | null; error: string | null; free: FreeStatus }>("/api/free/image", {
        method: "POST",
        body: JSON.stringify({ concept }),
      });
      if (data.free) onStatus(data.free);
      if (!data.image_url) {
        setError(data.error || "Görsel üretilemedi, tekrar dene.");
      } else {
        setResult({ url: data.image_url, concept });
        onCreated?.(data.image_url, concept);
      }
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="workspace">
      <form className="panel ws-panel" onSubmit={submit}>
        <h2>Ücretsiz görsel</h2>
        {!enabled && <div className="notice">Ücretsiz görsel üretimi çok yakında açılıyor. Şimdilik stok fotoğraf kütüphanesini kullanabilirsin.</div>}
        {enabled && left === 0 && (
          <div className="notice">
            <span>30 günlük {status?.images.limit} ücretsiz görsel hakkını kullandın. Stok kütüphanesi sınırsız; bir paketle daha yüksek kaliteli görsel üretebilirsin.</span>
            {upsell}
          </div>
        )}
        <div className="field">
          <label htmlFor="fg-concept">Ne görünsün?</label>
          <textarea
            id="fg-concept"
            required
            minLength={3}
            rows={5}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="Ahşap masada köpüklü latte, yanında kruvasan, sabah ışığı"
          />
          <span className="hint">Ürünü, ortamı ve ışığı yaz. Kare (1:1) formatta üretilir; yazı içeren görsellerde bu model zayıftır.</span>
        </div>
        <div className="generate">
          <button className="btn btn-primary btn-block" type="submit" disabled={loading || blocked}>
            {loading ? "Görsel üretiliyor…" : "Ücretsiz üret"}
          </button>
          <div className="cost">
            <span>Kredi harcamaz</span>
            {status && <span>{status.images.remaining}/{status.images.limit} hakkın var (30 gün)</span>}
          </div>
        </div>
      </form>

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>
          Sonuç
          {result && (
            <span style={{ display: "flex", gap: 6 }}>
              <a className="btn btn-ghost btn-sm" href={result.url} target="_blank" rel="noreferrer" download>
                İndir
              </a>
              {resultActions?.(result.url, result.concept)}
            </span>
          )}
        </h2>
        {error && <div className="notice error">{error}</div>}
        {loading ? (
          <div className="result-empty">
            <div>
              <div className="mark loading-mark" />
              Görsel üretiliyor, genelde 5–15 saniye sürer.
            </div>
          </div>
        ) : result ? (
          <div className="media-result">
            <img src={result.url} alt={result.concept} />
          </div>
        ) : (
          <div className="result-empty">
            <div>
              <div className="mark" />
              Ne görmek istediğini yaz, görsel burada görünecek.
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

/* ---------------- Stok fotoğraf kütüphanesi (Pexels) ---------------- */

const ORIENTATIONS: { value: "" | "square" | "portrait" | "landscape"; label: string }[] = [
  { value: "", label: "Tümü" },
  { value: "square", label: "Kare" },
  { value: "portrait", label: "Dikey" },
  { value: "landscape", label: "Yatay" },
];

const STARTERS = ["kahve", "beyaz eşya", "restoran", "emlak", "kuaför", "spor salonu", "moda", "çiçek"];

export function StockLibrary({
  enabled,
  onSave,
  saveLabel = "Dosyalarıma ekle",
  savedActions,
}: {
  enabled: boolean;
  /** Verilirse fotoğraf kullanıcının dosyalarına kopyalanır (giriş gerekir). */
  onSave?: (photo: StockPhoto) => Promise<string>;
  saveLabel?: string;
  savedActions?: (url: string, photo: StockPhoto) => ReactNode;
}) {
  const [query, setQuery] = useState("");
  const [orientation, setOrientation] = useState<(typeof ORIENTATIONS)[number]["value"]>("");
  const [result, setResult] = useState<StockResult | null>(null);
  const [lastQuery, setLastQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<StockPhoto | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<Record<number, string>>({});

  const search = async (q: string, page = 1, orient = orientation) => {
    if (q.trim().length < 2) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ q: q.trim(), page: String(page) });
      if (orient) params.set("orientation", orient);
      const data = await api<StockResult>(`/api/free/stock?${params}`);
      setResult((prev) => (page > 1 && prev ? { ...data, photos: [...prev.photos, ...data.photos] } : data));
      setLastQuery(q.trim());
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    search(query);
  };

  const save = async (photo: StockPhoto) => {
    if (!onSave) return;
    setSaving(true);
    setError("");
    try {
      const url = await onSave(photo);
      setSaved((s) => ({ ...s, [photo.id]: url }));
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  };

  if (!enabled) {
    return (
      <div className="panel empty">
        <h3>Stok fotoğraf kütüphanesi çok yakında</h3>
        <p>Telifsiz fotoğrafları burada arayıp ücretsiz indirebileceksin.</p>
      </div>
    );
  }

  return (
    <div className="stock">
      <form className="stock-search" onSubmit={submit}>
        <label className="search">
          <Icon name="search" size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ne arıyorsun? Örn. kahve, mutfak, gelinlik"
            aria-label="Fotoğraf ara"
          />
        </label>
        <div className="tabs" role="tablist" aria-label="Yön">
          {ORIENTATIONS.map((o) => (
            <button
              key={o.value}
              type="button"
              role="tab"
              aria-selected={orientation === o.value}
              className={orientation === o.value ? "active" : ""}
              onClick={() => {
                setOrientation(o.value);
                if (lastQuery) search(lastQuery, 1, o.value);
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
        <button className="btn btn-primary" type="submit" disabled={loading || query.trim().length < 2}>
          Ara
        </button>
      </form>

      {!result && !loading && (
        <div className="stock-starters">
          {STARTERS.map((s) => (
            <button
              key={s}
              type="button"
              className="chip"
              onClick={() => {
                setQuery(s);
                search(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {error && <div className="notice error">{error}</div>}

      {result && result.photos.length === 0 && (
        <div className="panel empty">
          <h3>"{lastQuery}" için fotoğraf bulunamadı</h3>
          <p>Daha genel bir kelime dene; İngilizce aramalar da daha çok sonuç verir.</p>
        </div>
      )}

      {result && result.photos.length > 0 && (
        <>
          <div className="stock-grid">
            {result.photos.map((p) => (
              <button
                key={p.id}
                type="button"
                className="stock-item"
                style={{ background: p.color || undefined, aspectRatio: `${p.width} / ${p.height}` }}
                onClick={() => setSelected(p)}
                aria-label={p.alt || `Fotoğraf: ${p.photographer}`}
              >
                <img src={p.thumb} alt={p.alt} loading="lazy" />
                <span className="by">{p.photographer}</span>
              </button>
            ))}
          </div>
          {result.has_more && (
            <div style={{ textAlign: "center", marginTop: 16 }}>
              <button className="btn btn-ghost" type="button" disabled={loading} onClick={() => search(lastQuery, result.page + 1)}>
                {loading ? "Yükleniyor…" : "Daha fazla göster"}
              </button>
            </div>
          )}
        </>
      )}

      <p className="stock-credit">
        Fotoğraflar <a href="https://www.pexels.com" target="_blank" rel="noreferrer">Pexels</a> kütüphanesinden; ücretsiz, ticari
        kullanım serbest. Fotoğrafçıyı anmak nazik bir jest.
      </p>

      {selected && (
        <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && setSelected(null)}>
          <div className="modal stock-modal" role="dialog" aria-modal="true" aria-label="Fotoğraf">
            <img src={selected.preview} alt={selected.alt} />
            <div className="stock-modal-foot">
              <div className="muted">
                <a href={selected.photographer_url} target="_blank" rel="noreferrer">
                  {selected.photographer}
                </a>{" "}
                · Pexels
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <a className="btn btn-ghost btn-sm" href={downloadUrl(selected)} target="_blank" rel="noreferrer">
                  İndir
                </a>
                {onSave &&
                  (saved[selected.id] ? (
                    savedActions?.(saved[selected.id], selected) ?? <span className="chip">Eklendi</span>
                  ) : (
                    <button className="btn btn-light btn-sm" type="button" disabled={saving} onClick={() => save(selected)}>
                      {saving ? "Ekleniyor…" : saveLabel}
                    </button>
                  ))}
                <button className="btn btn-ghost btn-sm" type="button" onClick={() => setSelected(null)}>
                  Kapat
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
