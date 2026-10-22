"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { api } from "../../lib/api";
import { onDownload } from "../../lib/download";
import { readHistory } from "../../lib/history";
import Icon from "../Icon";

export type LibraryItem = { id: string; kind: "image" | "video"; url: string; prompt: string; source?: string; created_at: string };

const SOURCE: Record<string, string> = { gorsel: "Görsel aracı", video: "Video aracı", sohbet: "Sohbet" };

/** Üretilen görsel/videolar: küçük resimli ızgara, her birinde indir butonu. */
export function LibraryGrid({ kind, onOpen }: { kind: "image" | "video"; onOpen?: (item: LibraryItem) => void }) {
  const [items, setItems] = useState<LibraryItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    api<{ items: LibraryItem[] }>(`/api/content/library?kind=${kind}&limit=120`)
      .then((d) => {
        if (!alive) return;
        // Bu tarayıcıdaki eski kayıtlar (sunucuya taşınmadan önce) da gösterilir
        const known = new Set(d.items.map((i) => i.url));
        const old = readHistory<{ url: string; concept: string }>(kind === "image" ? "gorsel" : "video")
          .filter((h) => h.data?.url?.startsWith("http") && !known.has(h.data.url))
          .map((h) => ({ id: `yerel-${h.id}`, kind, url: h.data.url, prompt: h.data.concept || h.title, created_at: new Date(h.at).toISOString() }));
        setItems([...d.items, ...old].sort((a, b) => b.created_at.localeCompare(a.created_at)));
      })
      .catch((e) => alive && setError(e.message || "Kütüphane yüklenemedi."));
    return () => {
      alive = false;
    };
  }, [kind]);

  const remove = async (item: LibraryItem) => {
    if (!window.confirm("Bu dosya kütüphaneden kaldırılsın mı?")) return;
    if (!item.id.startsWith("yerel-")) await api(`/api/content/library/${item.id}`, { method: "DELETE" }).catch(() => {});
    setItems((x) => (x || []).filter((i) => i.id !== item.id));
  };

  if (error) return <div className="notice error">{error}</div>;
  if (items === null) return <div className="library-grid loading" aria-busy="true" />;
  if (!items.length) {
    return (
      <div className="panel empty">
        <h3>Henüz {kind === "image" ? "görsel" : "video"} yok</h3>
        <p>Ürettiğin {kind === "image" ? "görseller (sohbette üretilenler dahil)" : "videolar"} burada birikir; buradan indirebilirsin.</p>
      </div>
    );
  }

  return (
    <div className={`library-grid ${kind}`}>
      {items.map((item) => (
        <figure key={item.id} className="library-item">
          <button type="button" className="thumb" onClick={() => onOpen?.(item)} aria-label="Büyük göster">
            {item.kind === "video" ? (
              <video src={`${item.url}#t=0.1`} muted playsInline preload="metadata" onMouseEnter={(e) => e.currentTarget.play().catch(() => {})} onMouseLeave={(e) => e.currentTarget.pause()} />
            ) : (
              <img src={item.url} alt={item.prompt} loading="lazy" />
            )}
          </button>
          <figcaption>
            <p title={item.prompt}>{item.prompt || "Adsız"}</p>
            <small>
              {new Date(item.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}
              {item.source && SOURCE[item.source] ? ` · ${SOURCE[item.source]}` : ""}
            </small>
          </figcaption>
          <div className="library-actions">
            <a className="btn btn-light btn-sm" href={item.url} download onClick={onDownload(item.url)}>
              <Icon name="download" size={14} /> İndir
            </a>
            {item.kind === "image" && (
              <Link className="btn btn-ghost btn-sm" href={`/araclar/video?konsept=${encodeURIComponent(item.prompt.slice(0, 300))}&gorsel=${encodeURIComponent(item.url)}`}>
                Videoya çevir
              </Link>
            )}
            <button type="button" className="icon-btn" aria-label="Kaldır" title="Kaldır" onClick={() => remove(item)}>
              <Icon name="close" size={14} />
            </button>
          </div>
        </figure>
      ))}
    </div>
  );
}
