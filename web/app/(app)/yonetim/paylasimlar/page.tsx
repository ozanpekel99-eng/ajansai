"use client";

// Yöneticiye özel: @ajansai.tr haftalık paylaşım planını (marketing/<hafta>/plan.json) kuyruğa aktar,
// her gönderiyi önizle, onayla / düzenle / atla. Yetki backend'de denetlenir (ADMIN_EMAILS);
// yönetici olmayan kullanıcı 403 alır ve bu sayfada bilgilendirme görür.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { api, ApiError } from "../../../lib/api";
import {
  CAPTION_MAX,
  KIND_LABEL,
  captionWarnings,
  countByStatus,
  formatLocal,
  fromInputValue,
  groupByWeek,
  hashtagCount,
  ImportResult,
  isVideo,
  normalizeMediaBase,
  parsePlan,
  SocialPost,
  statusLabel,
  toInputValue,
  upcomingMonday,
  weekFromPath,
  weekLabel,
} from "../../../lib/socialQueue";

export default function Paylasimlar() {
  const [posts, setPosts] = useState<SocialPost[] | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState("");
  const [showDone, setShowDone] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api<{ posts: SocialPost[] }>("/api/admin/social/queue");
      setPosts(d.posts);
      setError("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setForbidden(true);
      else setError(e instanceof Error ? e.message : "Kuyruk yüklenemedi.");
      setPosts((p) => p ?? []);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const replace = (p: SocialPost) => setPosts((list) => (list ? list.map((x) => (x.id === p.id ? p : x)) : list));

  if (forbidden) {
    return (
      <div className="page">
        <section className="panel empty">
          <h3>Bu sayfa yalnızca yöneticiler içindir</h3>
          <p>
            <Link href="/">Ana sayfaya dön</Link>
          </p>
        </section>
      </div>
    );
  }

  const groups = groupByWeek(posts || []);
  const now = Date.now();

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Konum">
        <span>Yönetim</span>
        <span aria-hidden> / </span>
        <strong>Paylaşım kuyruğu</strong>
      </nav>

      <div className="notice" style={{ marginBottom: 16 }}>
        <span>
          @ajansai.tr haftalık paylaşım planı. Onayladığın gönderiler, Instagram'a otomatik paylaşım açıldığında planlı saatinde paylaşılır
          (şu an kapalı: Meta <code>instagram_content_publish</code> izni bekleniyor). Düzenlenen gönderi yeniden onay bekler.
        </span>
      </div>

      <ImportPanel onImported={load} />

      {error && <div className="notice error" style={{ marginTop: 16 }}>{error}</div>}

      {posts === null ? (
        <p className="muted" style={{ marginTop: 24 }}>Yükleniyor…</p>
      ) : groups.length === 0 ? (
        <section className="panel empty" style={{ marginTop: 16 }}>
          <h3>Kuyrukta gönderi yok</h3>
          <p>Yukarıdan haftanın plan.json dosyasını aktar.</p>
        </section>
      ) : (
        <>
          <label className="social-toggle">
            <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Geçmiş haftaları da göster
          </label>
          {groups
            .filter((g, i) => showDone || i === 0 || g.posts.some((p) => new Date(p.scheduled_at).getTime() > now))
            .map((g) => {
              const c = countByStatus(g.posts);
              return (
                <section key={g.week} className="section">
                  <div className="section-head">
                    <div>
                      <h2>{weekLabel(g.week)}</h2>
                      <p>
                        {g.posts.length} gönderi · {c.approved || 0} onaylı · {c.pending || 0} onay bekliyor · {c.skipped || 0} atlandı
                        {c.published ? ` · ${c.published} paylaşıldı` : ""}
                      </p>
                    </div>
                  </div>
                  <div className="social-list">
                    {g.posts.map((p) => (
                      <PostCard key={p.id} post={p} onChange={replace} />
                    ))}
                  </div>
                </section>
              );
            })}
        </>
      )}
    </div>
  );
}

function ImportPanel({ onImported }: { onImported: () => void }) {
  const [open, setOpen] = useState(false);
  const [week, setWeek] = useState(upcomingMonday());
  const [mediaBase, setMediaBase] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setText(await file.text());
    const w = weekFromPath((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name);
    if (w) setWeek(w);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    let rows;
    try {
      rows = parsePlan(text);
    } catch (err) {
      setError((err as Error).message);
      return;
    }
    const base = normalizeMediaBase(mediaBase);
    if (base.error) {
      setError(base.error);
      return;
    }
    setBusy(true);
    try {
      const r = await api<ImportResult>("/api/admin/social/import", {
        method: "POST",
        body: JSON.stringify({ week, media_base: base.value, posts: rows }),
      });
      setResult(r);
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aktarılamadı.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="btn btn-light" onClick={() => setOpen(true)}>
        Haftanın planını aktar
      </button>
    );
  }

  return (
    <form className="panel ws-panel" onSubmit={submit}>
      <h2>Haftanın planını aktar</h2>
      <p className="muted" style={{ fontSize: 14, marginTop: 0 }}>
        <code>marketing/&lt;hafta&gt;/plan.json</code> dosyasını seç ya da içeriğini yapıştır. Aynı hafta yeniden aktarılırsa yalnızca onay
        bekleyen gönderiler güncellenir; onayladığın ya da atladığın gönderilere dokunulmaz.
      </p>
      <div className="field-row">
        <div className="field">
          <label htmlFor="sq-week">Hafta (pazartesi)</label>
          <input id="sq-week" type="date" required value={week} onChange={(e) => setWeek(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="sq-file">plan.json</label>
          <input id="sq-file" type="file" accept="application/json,.json" onChange={(e) => onFile(e.target.files?.[0])} />
        </div>
      </div>
      <div className="field">
        <label htmlFor="sq-base">Dosyaların herkese açık adresi</label>
        <input
          id="sq-base"
          inputMode="url"
          placeholder="https://…/marketing/2026-11-23"
          value={mediaBase}
          onChange={(e) => setMediaBase(e.target.value)}
        />
        <span className="muted" style={{ fontSize: 13 }}>
          plan.json'daki dosya adlarının (g1.png gibi) önüne eklenir. Plan tam https adresleri içeriyorsa boş bırak.
        </span>
      </div>
      <div className="field">
        <label htmlFor="sq-text">plan.json içeriği</label>
        <textarea id="sq-text" rows={6} value={text} onChange={(e) => setText(e.target.value)} placeholder='[{"day":"Pazartesi 23 Kasım","time":"12:30", …}]' />
      </div>
      {error && <p className="error-text">{error}</p>}
      {result && (
        <div className="notice" role="status">
          <span>
            {result.created} yeni, {result.updated} güncellendi, {result.kept} karar korundu.
            {result.warnings.map((w) => (
              <span key={w} style={{ display: "block", color: "#f5b945" }}>
                {w}
              </span>
            ))}
          </span>
        </div>
      )}
      <div className="actions" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="btn btn-primary" disabled={busy || !text.trim()}>
          {busy ? "Aktarılıyor…" : "Kuyruğa aktar"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
          Kapat
        </button>
      </div>
    </form>
  );
}

function PostCard({ post, onChange }: { post: SocialPost; onChange: (p: SocialPost) => void }) {
  const [editing, setEditing] = useState(false);
  const [caption, setCaption] = useState(post.caption);
  const [when, setWhen] = useState(toInputValue(post.scheduled_local));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  const status = statusLabel(post.status);
  const locked = post.status === "published";

  const call = async (path: string, init: RequestInit = { method: "POST" }) => {
    setBusy(true);
    setError("");
    try {
      const p = await api<SocialPost>(path, init);
      onChange(p);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "İşlem yapılamadı.");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    const local = fromInputValue(when);
    if (!local) {
      setError("Paylaşım zamanını seç.");
      return;
    }
    const body: Record<string, string> = {};
    if (caption !== post.caption) body.caption = caption;
    if (local !== post.scheduled_local) body.scheduled_local = local;
    if (!Object.keys(body).length) {
      setEditing(false);
      return;
    }
    if (await call(`/api/admin/social/${post.id}`, { method: "PUT", body: JSON.stringify(body) })) setEditing(false);
  };

  const startEdit = () => {
    setCaption(post.caption);
    setWhen(toInputValue(post.scheduled_local));
    setEditing(true);
  };

  const live = editing ? captionWarnings(caption) : [];

  return (
    <article className={`panel social-card status-${post.status}`}>
      <div className="social-media" aria-label={`${post.media.length} dosya`}>
        {post.media.map((url, i) =>
          isVideo(url) ? (
            <video key={url + i} src={url} controls muted playsInline preload="metadata" />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={url + i} src={url} alt={`${post.title} ${i + 1}`} loading="lazy" />
          ),
        )}
      </div>
      <div className="social-body">
        <div className="social-meta">
          <span className={`status-pill ${status.tone}`}>{status.text}</span>
          <span className="chip chip-muted">{KIND_LABEL[post.kind] || post.kind}{post.kind === "carousel" ? ` (${post.media.length})` : ""}</span>
          {post.target && <span className="chip chip-soft">{post.target}</span>}
          <span className="muted social-when">{formatLocal(post.scheduled_local)}</span>
        </div>
        <h3>{post.title || "Başlıksız"}</h3>

        {editing ? (
          <>
            <div className="field">
              <label htmlFor={`when-${post.id}`}>Paylaşım zamanı (İstanbul)</label>
              <input id={`when-${post.id}`} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor={`cap-${post.id}`}>Açıklama</label>
              <textarea id={`cap-${post.id}`} rows={10} value={caption} onChange={(e) => setCaption(e.target.value)} />
              <span className="muted" style={{ fontSize: 13 }}>
                {caption.length}/{CAPTION_MAX} karakter · {hashtagCount(caption)}/30 etiket
              </span>
            </div>
            {live.map((w) => (
              <p key={w} className="error-text">{w}</p>
            ))}
          </>
        ) : (
          <p className={`social-caption ${expanded ? "open" : ""}`} onClick={() => setExpanded((v) => !v)}>
            {post.caption}
          </p>
        )}

        {!editing && post.problems.length > 0 && (
          <ul className="social-problems">
            {post.problems.map((p) => (
              <li key={p} className="error-text">{p}</li>
            ))}
          </ul>
        )}
        {post.error && <p className="error-text">Paylaşım hatası: {post.error}</p>}
        {post.approved_by && post.status === "approved" && <p className="muted" style={{ fontSize: 13 }}>Onaylayan: {post.approved_by}</p>}
        {error && <p className="error-text">{error}</p>}

        {!locked && (
          <div className="social-actions">
            {editing ? (
              <>
                <button className="btn btn-primary btn-sm" disabled={busy || live.length > 0} onClick={save}>
                  {busy ? "Kaydediliyor…" : "Kaydet"}
                </button>
                <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => setEditing(false)}>
                  Vazgeç
                </button>
              </>
            ) : (
              <>
                {post.status !== "approved" && (
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={busy || post.problems.length > 0}
                    title={post.problems.length ? "Önce sorunları düzelt" : undefined}
                    onClick={() => call(`/api/admin/social/${post.id}/approve`)}
                  >
                    Onayla
                  </button>
                )}
                <button className="btn btn-light btn-sm" disabled={busy} onClick={startEdit}>
                  Düzenle
                </button>
                {post.status !== "skipped" && (
                  <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => call(`/api/admin/social/${post.id}/skip`)}>
                    Atla
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
