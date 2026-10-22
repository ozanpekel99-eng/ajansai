"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, api } from "../../lib/api";
import { readHistory } from "../../lib/history";
import { money } from "../../lib/plans";
import { useSession } from "../../lib/session";
import { UploadProgress, useUploader } from "../Attachments";
import { ChipSelect } from "../Controls";
import Icon from "../Icon";
import { EmptyResult, LockedNotice, WorkspaceProps } from "./common";

type AdAccount = { account_id: string; name: string; currency: string; account_status: number; status_label?: string; usable?: boolean; billing_url?: string };
type Page = { id: string; name: string; instagram_id?: string | null; instagram_username?: string | null; source?: string };
type IgAccount = { id: string; username: string; page_id?: string | null };
type Loc = { key: string; name: string; type: "country" | "region" | "city"; country_code?: string | null; region?: string | null };
type Media = { url: string; kind: "image" | "video" };
type Objective = "profile" | "traffic" | "whatsapp" | "instagram_dm" | "awareness";
type Goal = "traffic" | "message" | "awareness";
type Insights = { spend: number; impressions: number; reach: number; clicks: number; ctr: number; cpc: number; conversations: number };
type AdRow = {
  id: string;
  name: string;
  objective: Objective;
  daily_budget: number;
  currency: string;
  media_url: string | null;
  status: string;
  insights: Insights | null;
  error?: string;
  campaign_id: string;
  ad_account_id: string;
  created_at: string;
};

const OBJECTIVES: { value: Objective; label: string; note: string }[] = [
  { value: "profile", label: "Trafik (Profil ziyareti)", note: "Instagram profiline ziyaret getirir" },
  { value: "traffic", label: "Trafik (Web sitesi)", note: "Sitene tıklama getirir" },
  { value: "whatsapp", label: "Mesaj (WhatsApp)", note: "Sana WhatsApp'tan yazarlar" },
  { value: "instagram_dm", label: "Mesaj (Instagram DM)", note: "Sana Instagram'dan mesaj atarlar" },
  { value: "awareness", label: "Bilinirlik", note: "Olabildiğince çok kişiye gösterir" },
];

const GOALS: { value: Goal; label: string; note: string }[] = [
  { value: "traffic", label: "Trafik (Profil ziyareti)", note: "Instagram profiline ya da web sitene ziyaret getirir" },
  { value: "message", label: "Mesaj", note: "WhatsApp'tan ya da Instagram DM'den sana yazarlar" },
  { value: "awareness", label: "Bilinirlik", note: "Olabildiğince çok kişiye gösterir" },
];

const goalOf = (o: Objective): Goal => (o === "profile" || o === "traffic" ? "traffic" : o === "awareness" ? "awareness" : "message");
const isMessage = (o: Objective) => o === "whatsapp" || o === "instagram_dm";
const needsLink = (o: Objective) => o === "traffic" || o === "awareness";

const CTAS = [
  { value: "LEARN_MORE", label: "Daha fazla bilgi" },
  { value: "SHOP_NOW", label: "Alışverişe başla" },
  { value: "ORDER_NOW", label: "Sipariş ver" },
  { value: "BOOK_NOW", label: "Rezervasyon yap" },
  { value: "CONTACT_US", label: "Bize ulaşın" },
  { value: "GET_OFFER", label: "Teklifi al" },
  { value: "SIGN_UP", label: "Kaydol" },
];

const STATUS: Record<string, { label: string; cls: string }> = {
  ACTIVE: { label: "Yayında", cls: "success" },
  PAUSED: { label: "Duraklatıldı", cls: "pending" },
  CAMPAIGN_PAUSED: { label: "Duraklatıldı", cls: "pending" },
  IN_PROCESS: { label: "İnceleniyor", cls: "pending" },
  PENDING_REVIEW: { label: "Meta incelemesinde", cls: "pending" },
  WITH_ISSUES: { label: "Sorunlu", cls: "failure" },
  DISAPPROVED: { label: "Reddedildi", cls: "failure" },
  DELETED: { label: "Silindi", cls: "failure" },
  ARCHIVED: { label: "Arşivlendi", cls: "pending" },
};

const AGES = Array.from({ length: 48 }, (_, i) => i + 18);
const today = () => new Date().toISOString().slice(0, 10);

type Placement =
  | "instagram_feed" | "instagram_story" | "instagram_reels" | "instagram_explore"
  | "facebook_feed" | "facebook_story" | "facebook_reels";
const PLACEMENT_GROUPS: { platform: "instagram" | "facebook"; label: string; items: { value: Placement; label: string }[] }[] = [
  {
    platform: "instagram",
    label: "Instagram",
    items: [
      { value: "instagram_feed", label: "Akış (gönderi)" },
      { value: "instagram_story", label: "Hikâye" },
      { value: "instagram_reels", label: "Reels" },
      { value: "instagram_explore", label: "Keşfet" },
    ],
  },
  {
    platform: "facebook",
    label: "Facebook",
    items: [
      { value: "facebook_feed", label: "Akış (gönderi)" },
      { value: "facebook_story", label: "Hikâye" },
      { value: "facebook_reels", label: "Reels" },
    ],
  },
];
const ALL_PLACEMENTS = PLACEMENT_GROUPS.flatMap((g) => g.items);
const DEFAULT_PLACEMENTS: Placement[] = ["instagram_feed", "instagram_story", "instagram_reels", "instagram_explore"];
const isVertical = (p: Placement) => /story|reels/.test(p);
// Profil ziyareti ve Instagram DM yalnızca Instagram'da çalışır
const igOnly = (o: Objective) => o === "profile" || o === "instagram_dm";

export default function ReklamWorkspace(_: WorkspaceProps) {
  const { usage, metaConnected, refresh } = useSession();
  const [view, setView] = useState<"new" | "list">("new");
  const [error, setError] = useState("");

  const connect = async () => {
    setError("");
    try {
      const d = await api<{ oauth_url: string }>("/api/ads/meta/connect");
      window.location.href = d.oauth_url;
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const disconnect = async () => {
    await api("/api/ads/meta/connection", { method: "DELETE" });
    refresh();
  };

  if (usage && !usage.ads_enabled) {
    return <LockedNotice text="Meta reklam entegrasyonu Pro ve Advanced paketlerinde açılır." plan="pro" />;
  }

  if (!metaConnected) {
    return (
      <div className="panel ws-panel" style={{ maxWidth: 560 }}>
        <h2>Meta hesabını bağla</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Facebook hesabınla giriş yaparsın; reklam bütçesi kendi reklam hesabından harcanır. Reklamlar yalnızca Instagram'da
          gösterilir ve sen "Yayına al" demeden yayına girmez.
        </p>
        <ol className="connect-tips">
          <li>Açılan Meta ekranında devam et.</li>
          <li>
            İzin ekranında <strong>reklam hesabını, Facebook sayfanı ve Instagram hesabını</strong> işaretle (gerekirse &quot;Ayarları
            düzenle&quot; ile tümünü seç).
          </li>
          <li>Eksik bir şey varsa (kart, sayfa, Instagram) burada adım adım gösteririz.</li>
        </ol>
        {error && <div className="notice error">{error}</div>}
        <button className="btn btn-primary btn-block" onClick={connect}>
          Meta ile bağlan
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="ws-title" style={{ marginBottom: 16 }}>
        <div className="segmented small" role="tablist" aria-label="Reklam görünümü">
          <button type="button" role="tab" aria-selected={view === "new"} className={view === "new" ? "active" : ""} onClick={() => setView("new")}>
            Yeni reklam
          </button>
          <button type="button" role="tab" aria-selected={view === "list"} className={view === "list" ? "active" : ""} onClick={() => setView("list")}>
            Reklamlarım
          </button>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={disconnect}>
          Meta bağlantısını kaldır
        </button>
      </div>
      <SetupChecklist onReconnect={connect} />
      {view === "new" ? <NewAd onCreated={() => setView("list")} /> : <AdList />}
    </>
  );
}

/* ---------------- Hazırlık kontrolü ---------------- */

type SetupStep = { key: string; done: boolean; title: string; text: string; action: string; url: string };

function SetupChecklist({ onReconnect }: { onReconnect: () => void }) {
  const [data, setData] = useState<{ ready: boolean; steps: SetupStep[] } | null>(null);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);

  const check = async () => {
    setChecking(true);
    setError("");
    try {
      setData(await api("/api/ads/meta/setup"));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    check();
    // Kullanıcı Meta sekmesinden dönünce otomatik tekrar kontrol
    const onFocus = () => document.visibilityState === "visible" && check();
    document.addEventListener("visibilitychange", onFocus);
    return () => document.removeEventListener("visibilitychange", onFocus);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <div className="notice error" style={{ marginBottom: 16 }}>
        <span>Meta hesabın kontrol edilemedi: {error}</span>
        <button type="button" className="btn btn-light btn-sm" onClick={onReconnect}>
          Yeniden bağlan
        </button>
      </div>
    );
  }
  if (!data || data.ready) return null;
  const left = data.steps.filter((s) => !s.done).length;
  return (
    <section className="panel setup-list" aria-label="Reklam hazırlığı">
      <div className="setup-head">
        <div>
          <h3>Reklam vermeden önce {left} adım kaldı</h3>
          <p className="muted">Her adım Meta&apos;nın kendi sayfasında açılır; bitirip buraya dönünce otomatik kontrol ederiz.</p>
        </div>
        <button type="button" className="btn btn-light btn-sm" onClick={check} disabled={checking}>
          {checking ? "Kontrol ediliyor…" : "Tekrar kontrol et"}
        </button>
      </div>
      <ol>
        {data.steps.map((s) => (
          <li key={s.key} className={s.done ? "done" : ""}>
            <span className="setup-mark" aria-hidden="true">{s.done ? "✓" : ""}</span>
            <div>
              <strong>{s.title}</strong>
              <p>{s.text}</p>
            </div>
            {!s.done && (
              <a className="btn btn-primary btn-sm" href={s.url} target="_blank" rel="noreferrer">
                {s.action}
              </a>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

/* ---------------- Yeni reklam ---------------- */

function NewAd({ onCreated }: { onCreated: () => void }) {
  const { refresh } = useSession();
  const [accounts, setAccounts] = useState<AdAccount[]>([]);
  const [pages, setPages] = useState<Page[]>([]);
  const [igAccounts, setIgAccounts] = useState<IgAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  const [pageId, setPageId] = useState("");
  const [igId, setIgId] = useState("");
  const [objective, setObjective] = useState<Objective>("profile");
  const [wa, setWa] = useState<{ number: string | null; connect_url: string; help: string } | null>(null);
  const [waLoading, setWaLoading] = useState(false);
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("250");
  const [startDate, setStartDate] = useState(today());
  const [endDate, setEndDate] = useState("");
  const [locations, setLocations] = useState<Loc[]>([{ key: "TR", name: "Türkiye", type: "country", country_code: "TR" }]);
  const [ageMin, setAgeMin] = useState(18);
  const [ageMax, setAgeMax] = useState(65);
  const [gender, setGender] = useState<"all" | "male" | "female">("all");
  const [media, setMedia] = useState<Media | null>(null);
  const [storyMedia, setStoryMedia] = useState<Media | null>(null);
  const [placements, setPlacements] = useState<Placement[]>(DEFAULT_PLACEMENTS);
  const [previewAt, setPreviewAt] = useState<Placement>("instagram_feed");
  const [primaryText, setPrimaryText] = useState("");
  const [headline, setHeadline] = useState("");
  const [link, setLink] = useState("");
  const [cta, setCta] = useState("LEARN_MORE");
  const [brief, setBrief] = useState("");
  const [writing, setWriting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  const account = accounts.find((a) => a.account_id === accountId);
  const igUsername = igAccounts.find((a) => a.id === igId)?.username || "";

  const checkWa = () => {
    if (!pageId) return;
    setWaLoading(true);
    api<{ number: string | null; connect_url: string; help: string }>(`/api/ads/meta/whatsapp?page_id=${pageId}`)
      .then(setWa)
      .catch(() => setWa(null))
      .finally(() => setWaLoading(false));
  };

  useEffect(() => {
    if (objective === "whatsapp" && pageId) checkWa();
  }, [objective, pageId]); // eslint-disable-line react-hooks/exhaustive-deps
  const currency = account?.currency || "TRY";

  const usable = (a: AdAccount) => a.usable ?? a.account_status === 1;

  useEffect(() => {
    api<{ ad_accounts: AdAccount[] }>("/api/ads/meta/ad-accounts")
      .then((a) => {
        setAccounts(a.ad_accounts);
        const first = a.ad_accounts.find((x) => x.account_status === 1) || a.ad_accounts.find(usable);
        if (first) setAccountId(first.account_id);
      })
      .catch((e) => setLoadError((e as ApiError).message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reklam hesabı değişince: o hesabın tanıtabildiği sayfalar ve bağlı Instagram hesapları gelir,
  // sayfa ile Instagram birbirine göre otomatik eşlenir.
  useEffect(() => {
    if (!accountId) return;
    setIgAccounts([]);
    setIgId("");
    Promise.all([
      api<{ pages: Page[] }>(`/api/ads/meta/pages?ad_account_id=${accountId}`).catch(() => ({ pages: [] as Page[] })),
      api<{ accounts: IgAccount[] }>(`/api/ads/meta/instagram-accounts?ad_account_id=${accountId}`).catch(() => ({ accounts: [] as IgAccount[] })),
    ]).then(([p, ig]) => {
      setPages(p.pages);
      setIgAccounts(ig.accounts);
      // Önce Instagram'ı bağlı olan sayfa, yoksa reklam hesabının sayfası, yoksa ilk sayfa
      const withIg = p.pages.find((x) => x.instagram_id);
      const page = withIg || p.pages.find((x) => x.source === "ad_account") || p.pages[0];
      const igLinked = ig.accounts.find((a) => a.page_id && a.page_id === page?.id) || ig.accounts.find((a) => a.id === page?.instagram_id) || ig.accounts[0];
      if (igLinked) {
        setIgId(igLinked.id);
        setPageId(igLinked.page_id || page?.id || "");
      } else if (page) {
        setPageId(page.id);
      }
    });
  }, [accountId]);

  const writeCopy = async () => {
    if (!brief.trim()) {
      setError("Önce ürün veya kampanyayı kısaca anlat, metni ona göre yazayım.");
      return;
    }
    setWriting(true);
    setError("");
    try {
      const d = await api<{ primary_text: string; headline: string }>("/api/ads/meta/ad-copy", {
        method: "POST",
        body: JSON.stringify({ brief, objective }),
      });
      setPrimaryText(d.primary_text);
      setHeadline(d.headline);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setWriting(false);
      refresh();
    }
  };

  const days = useMemo(() => {
    if (!endDate) return null;
    const d = Math.round((new Date(endDate).getTime() - new Date(startDate || today()).getTime()) / 86400000) + 1;
    return d > 0 ? d : null;
  }, [startDate, endDate]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!media) {
      setError("Gönderi için bir görsel veya video seç.");
      return;
    }
    if (!activePlacements.length) {
      setError("En az bir reklam alanı işaretle.");
      return;
    }
    if (storyMedia && storyMedia.kind !== media.kind) {
      setError("Gönderi ve hikâye dosyası aynı türde olmalı: ikisi de görsel ya da ikisi de video.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api("/api/ads/meta/ads", {
        method: "POST",
        body: JSON.stringify({
          ad_account_id: accountId,
          page_id: pageId,
          instagram_user_id: igId || null,
          name,
          objective,
          daily_budget: Number(budget),
          currency,
          start_date: startDate || null,
          end_date: endDate || null,
          locations,
          age_min: ageMin,
          age_max: ageMax,
          gender,
          media,
          story_media: storyMedia && activePlacements.some(isVertical) ? storyMedia : null,
          placements: activePlacements,
          primary_text: primaryText,
          headline,
          link: needsLink(objective) ? link : objective === "profile" && igUsername ? `https://www.instagram.com/${igUsername}/` : null,
          call_to_action: cta,
        }),
      });
      refresh();
      onCreated();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  };

  if (loadError) return <div className="notice error">{loadError}</div>;

  // Hedefe uymayan alanlar (ör. profil ziyaretinde Facebook) gönderilmez
  const activePlacements = placements.filter((p) => !(igOnly(objective) && p.startsWith("facebook")));
  const togglePlacement = (p: Placement) =>
    setPlacements((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]));
  const shownPreview: Placement = activePlacements.includes(previewAt) ? previewAt : activePlacements[0] || "instagram_feed";
  const pageName = pages.find((p) => p.id === pageId)?.name || "Sayfan";
  const ctaLabel =
    objective === "whatsapp"
      ? "WhatsApp'tan mesaj gönder"
      : objective === "instagram_dm"
        ? "Mesaj gönder"
        : objective === "profile"
          ? "Profili ziyaret et"
          : CTAS.find((c) => c.value === cta)?.label || "Daha fazla bilgi al";
  const igName = igAccounts.find((a) => a.id === igId)?.username || pages.find((p) => p.id === pageId)?.name || "hesabin";

  return (
    <form className="ad-builder" onSubmit={submit}>
      <div className="ad-steps">
        <section className="panel ws-panel">
          <h2>1. Hesaplar</h2>
          <div className="field">
            <label htmlFor="ad-account">Reklam hesabı</label>
            <select id="ad-account" value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
              <option value="" disabled>
                {accounts.length ? "Seç" : "Yükleniyor…"}
              </option>
              {accounts.map((a) => (
                <option key={a.account_id} value={a.account_id} disabled={!usable(a)}>
                  {a.name} ({a.currency}){a.account_status !== 1 ? ` · ${a.account_status === 3 ? "ödenmemiş bakiye" : a.account_status === 9 ? "ödeme ek süresinde" : (a.status_label || "aktif değil").toLowerCase()}` : ""}
                </option>
              ))}
            </select>
            {account && account.account_status !== 1 && usable(account) && (
              <div className="notice" style={{ marginTop: 8 }}>
                <span>{account.status_label}. Reklamı yine de hazırlayabilirsin.</span>
                {account.billing_url && (
                  <a className="btn btn-light btn-sm" href={account.billing_url} target="_blank" rel="noreferrer">
                    Bakiyeyi öde
                  </a>
                )}
              </div>
            )}
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="ad-page">Facebook sayfası</label>
              <select
                id="ad-page"
                value={pageId}
                onChange={(e) => {
                  setPageId(e.target.value);
                  const pg = pages.find((x) => x.id === e.target.value);
                  const ig = igAccounts.find((a) => a.page_id === pg?.id) || igAccounts.find((a) => a.id === pg?.instagram_id);
                  if (ig) setIgId(ig.id);
                }}
                required
              >
                {!pages.length && <option value="">Sayfa bulunamadı</option>}
                {pages.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.instagram_username ? ` · @${p.instagram_username}` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="ad-ig">Instagram hesabı</label>
              <select
                id="ad-ig"
                value={igId}
                onChange={(e) => {
                  setIgId(e.target.value);
                  const linked = igAccounts.find((a) => a.id === e.target.value)?.page_id;
                  if (linked) setPageId(linked);
                }}
              >
                <option value="">Sayfa adına yayınla</option>
                {igAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    @{a.username}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <span className="hint">
            Reklam yalnızca Instagram&apos;da gösterilir: akış, hikâye, Reels ve keşfet. Aradığın sayfa ya da Instagram listede yoksa Meta izin
            ekranında seçilmemiştir; &quot;Meta bağlantısını kaldır&quot; deyip yeniden bağlanırken hepsini işaretle.
          </span>
        </section>

        <section className="panel ws-panel">
          <h2>2. Amaç</h2>
          <div className="objective-cards">
            {GOALS.map((g) => (
              <button
                type="button"
                key={g.value}
                className={goalOf(objective) === g.value ? "active" : ""}
                aria-pressed={goalOf(objective) === g.value}
                onClick={() => setObjective(g.value === "traffic" ? "profile" : g.value === "message" ? "whatsapp" : "awareness")}
              >
                <strong>{g.label}</strong>
                <small>{g.note}</small>
              </button>
            ))}
          </div>
          {goalOf(objective) === "traffic" && (
            <div className="field">
              <label>Ziyaretçiler nereye gitsin?</label>
              <div className="segmented small" role="tablist">
                <button type="button" className={objective === "profile" ? "active" : ""} onClick={() => setObjective("profile")}>
                  Instagram profili
                </button>
                <button type="button" className={objective === "traffic" ? "active" : ""} onClick={() => setObjective("traffic")}>
                  Web sitesi
                </button>
              </div>
              {objective === "profile" && !igId && <span className="error-text">Profil ziyareti için yukarıdan bir Instagram hesabı seç.</span>}
            </div>
          )}
          {goalOf(objective) === "message" && (
            <div className="field">
              <label>Mesajlar nereden gelsin?</label>
              <div className="segmented small" role="tablist">
                <button type="button" className={objective === "whatsapp" ? "active" : ""} onClick={() => setObjective("whatsapp")}>
                  WhatsApp
                </button>
                <button type="button" className={objective === "instagram_dm" ? "active" : ""} onClick={() => setObjective("instagram_dm")}>
                  Instagram DM
                </button>
              </div>
              {objective === "whatsapp" &&
                (waLoading ? (
                  <span className="hint">WhatsApp numarası kontrol ediliyor…</span>
                ) : wa?.number ? (
                  <span className="hint">
                    Bağlı WhatsApp numarası: <strong>{wa.number}</strong>
                  </span>
                ) : wa ? (
                  <div className="notice" style={{ marginTop: 8 }}>
                    <span>Bu Facebook sayfasına bağlı WhatsApp numarası bulunamadı. {wa.help}</span>
                    <span style={{ display: "flex", gap: 6 }}>
                      <a className="btn btn-primary btn-sm" href={wa.connect_url} target="_blank" rel="noreferrer">
                        WhatsApp&apos;ı bağla
                      </a>
                      <button type="button" className="btn btn-light btn-sm" onClick={checkWa}>
                        Tekrar kontrol et
                      </button>
                    </span>
                  </div>
                ) : null)}
              {objective === "instagram_dm" && !igId && <span className="error-text">Instagram DM için yukarıdan bir Instagram hesabı seç.</span>}
            </div>
          )}
          <div className="field">
            <label htmlFor="ad-name">Kampanya adı</label>
            <input id="ad-name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Kasım buzdolabı kampanyası" />
          </div>
        </section>

        <section className="panel ws-panel">
          <h2>3. Kitle</h2>
          <LocationPicker value={locations} onChange={setLocations} />
          <div className="field-row">
            <div className="field">
              <label htmlFor="age-min">Yaş</label>
              <div className="age-row">
                <select id="age-min" value={ageMin} onChange={(e) => setAgeMin(Number(e.target.value))}>
                  {AGES.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
                <span>–</span>
                <select aria-label="Maksimum yaş" value={ageMax} onChange={(e) => setAgeMax(Number(e.target.value))}>
                  {AGES.map((a) => (
                    <option key={a} value={a}>
                      {a === 65 ? "65+" : a}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field">
              <label>Cinsiyet</label>
              <div className="segmented">
                {[
                  ["all", "Tümü"],
                  ["female", "Kadın"],
                  ["male", "Erkek"],
                ].map(([v, l]) => (
                  <button type="button" key={v} className={gender === v ? "active" : ""} aria-pressed={gender === v} onClick={() => setGender(v as typeof gender)}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="panel ws-panel">
          <h2>4. Bütçe ve süre</h2>
          <div className="field-row">
            <div className="field">
              <label htmlFor="ad-budget">Günlük bütçe ({currency})</label>
              <input id="ad-budget" type="number" min={1} step="1" required value={budget} onChange={(e) => setBudget(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="ad-start">Başlangıç</label>
              <input id="ad-start" type="date" min={today()} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="ad-end">Bitiş (isteğe bağlı)</label>
              <input id="ad-end" type="date" min={startDate || today()} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
          <span className="hint">
            {days
              ? `Toplam en fazla ${money(Number(budget || 0) * days, currency)} (${days} gün). `
              : "Bitiş tarihi vermezsen sen durdurana kadar günlük bütçe kadar harcar. "}
            Bütçe kendi Meta reklam hesabından harcanır; ajansAI kredisi harcamaz.
          </span>
        </section>

        <section className="panel ws-panel">
          <h2>5. Reklam alanları ve görseller</h2>
          <div className="placement-groups">
            {PLACEMENT_GROUPS.map((g) => {
              const blocked = g.platform === "facebook" && igOnly(objective);
              return (
                <fieldset key={g.platform} className={`placement-group ${blocked ? "blocked" : ""}`} disabled={blocked}>
                  <legend>{g.label}</legend>
                  {g.items.map((it) => (
                    <label key={it.value} className="check">
                      <input
                        type="checkbox"
                        checked={!blocked && placements.includes(it.value)}
                        onChange={() => togglePlacement(it.value)}
                      />
                      {it.label}
                    </label>
                  ))}
                  {blocked && <small>{objective === "profile" ? "Profil ziyareti" : "Instagram DM"} yalnızca Instagram'da çalışır.</small>}
                </fieldset>
              );
            })}
          </div>
          <MediaPicker
            title="Gönderi görseli · akış ve keşfet"
            hint="Kare (1:1) veya dikdörtgen (4:5) en iyisi."
            value={media}
            onChange={setMedia}
          />
          {activePlacements.some(isVertical) && (
            <MediaPicker
              title="Hikâye ve Reels görseli · isteğe bağlı"
              hint="Dikey (9:16) yükle; hikâye ve Reels'te bu, akışta gönderi görseli gösterilir. Boş bırakırsan her yerde gönderi görseli kullanılır."
              value={storyMedia}
              onChange={setStoryMedia}
            />
          )}
        </section>

        <section className="panel ws-panel">
          <h2>6. Reklam metni</h2>
          <div className="field">
            <label htmlFor="ad-brief">Yapay zekaya anlat (isteğe bağlı)</label>
            <div className="inline-row">
              <input
                id="ad-brief"
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="Çorlu'da No-Frost buzdolabında peşin fiyatına 6 taksit"
              />
              <button type="button" className="btn btn-light btn-sm" onClick={writeCopy} disabled={writing}>
                <Icon name="sparkle" size={14} /> {writing ? "Yazılıyor…" : "Metni yaz · 1 kredi"}
              </button>
            </div>
          </div>
          <div className="field">
            <label htmlFor="ad-text">Ana metin</label>
            <textarea id="ad-text" required rows={4} value={primaryText} onChange={(e) => setPrimaryText(e.target.value)} maxLength={2000} />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="ad-headline">Başlık</label>
              <input id="ad-headline" value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={120} />
            </div>
            {needsLink(objective) && (
              <div className="field">
                <label>Buton</label>
                <ChipSelect icon="arrowUp" label="Buton" value={cta} onChange={setCta} options={CTAS} />
              </div>
            )}
          </div>
          {needsLink(objective) ? (
            <div className="field">
              <label htmlFor="ad-link">Web sitesi bağlantısı</label>
              <input id="ad-link" required inputMode="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://www.siten.com/kampanya" />
            </div>
          ) : (
            <span className="hint">
              {objective === "whatsapp"
                ? "Buton \"WhatsApp'tan mesaj gönder\" olur; Facebook sayfana bağlı WhatsApp numarası kullanılır."
                : objective === "instagram_dm"
                  ? "Buton \"Mesaj gönder\" olur; mesajlar Instagram DM kutuna gelir."
                  : "Reklama tıklayan kişi Instagram profiline gider."}
            </span>
          )}
        </section>
      </div>

      <aside className="ad-preview-col">
        <div className="panel ws-panel ad-preview-panel">
          <h2>Önizleme</h2>
          <div className="preview-tabs" role="tablist" aria-label="Reklam alanı önizlemesi">
            {ALL_PLACEMENTS.filter((p) => activePlacements.includes(p.value)).map((p) => (
              <button
                key={p.value}
                type="button"
                role="tab"
                aria-selected={shownPreview === p.value}
                className={shownPreview === p.value ? "active" : ""}
                onClick={() => setPreviewAt(p.value)}
              >
                {p.value.startsWith("facebook") ? "FB" : "IG"} {p.label.replace(" (gönderi)", "")}
              </button>
            ))}
          </div>
          <AdPreview
            placement={shownPreview}
            media={isVertical(shownPreview) && storyMedia ? storyMedia : media}
            name={shownPreview.startsWith("facebook") ? pageName : igName}
            text={primaryText}
            headline={headline}
            cta={ctaLabel}
          />
          {error && <div className="notice error">{error}</div>}
          <button className="btn btn-primary btn-block" type="submit" disabled={saving || !accountId}>
            {saving ? (media?.kind === "video" ? "Video Meta'ya yükleniyor…" : "Reklam oluşturuluyor…") : "Reklamı oluştur (duraklatılmış)"}
          </button>
          <p className="faint" style={{ fontSize: 12.5, margin: "8px 0 0" }}>
            Reklam Meta'da duraklatılmış oluşturulur. Reklamlarım sekmesinden "Yayına al" dediğinde harcama başlar.
          </p>
        </div>
      </aside>
    </form>
  );
}

function LocationPicker({ value, onChange }: { value: Loc[]; onChange: (v: Loc[]) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Loc[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    clearTimeout(timer.current);
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    timer.current = setTimeout(() => {
      api<{ locations: Loc[] }>(`/api/ads/meta/locations?q=${encodeURIComponent(q.trim())}`)
        .then((d) => setResults(d.locations))
        .catch(() => setResults([]));
    }, 300);
  }, [q]);

  const add = (loc: Loc) => {
    // Ülke dışında bir konum eklenince varsayılan "Türkiye" kaldırılır.
    const base = loc.type === "country" ? value : value.filter((v) => v.type !== "country");
    if (!base.some((v) => v.key === loc.key)) onChange([...base, loc]);
    setQ("");
    setResults([]);
  };

  const label = (l: Loc) => (l.type === "city" ? `${l.name}${l.region ? `, ${l.region}` : ""} (+10 km)` : l.name);

  return (
    <div className="field">
      <label htmlFor="ad-loc">Konum</label>
      <div className="loc-chips">
        {value.map((l) => (
          <span key={l.key} className="chip chip-soft">
            {label(l)}
            <button type="button" aria-label={`${l.name} kaldır`} onClick={() => onChange(value.filter((v) => v.key !== l.key))}>
              <Icon name="close" size={12} />
            </button>
          </span>
        ))}
      </div>
      <div className="loc-search">
        <input id="ad-loc" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Şehir veya ilçe ara: Çorlu, Kadıköy, İzmir…" autoComplete="off" />
        {results.length > 0 && (
          <ul>
            {results.map((r) => (
              <li key={r.key}>
                <button type="button" onClick={() => add(r)}>
                  {label(r)} <small>{r.type === "city" ? "Şehir/ilçe" : r.type === "region" ? "İl" : "Ülke"}</small>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function MediaPicker({ value, onChange, title, hint }: { value: Media | null; onChange: (m: Media | null) => void; title: string; hint: string }) {
  const up = useUploader(["image", "video"], 1, 0, (f) => onChange({ url: f.url, kind: f.kind === "video" ? "video" : "image" }));
  const library = useMemo(() => {
    const imgs = readHistory<{ url: string }>("gorsel").map((h) => ({ url: h.data.url, kind: "image" as const }));
    const vids = readHistory<{ url: string }>("video").map((h) => ({ url: h.data.url, kind: "video" as const }));
    return [...imgs, ...vids].filter((m) => m.url && m.url.startsWith("https://")).slice(0, 12);
  }, []);

  return (
    <div className="field">
      <label>{title}</label>
      {up.field}
      <div className="media-grid">
        <button type="button" className="media-upload" onClick={up.pick} disabled={up.busy.length > 0}>
          <Icon name="plus" size={20} />
          <span>{up.busy.length ? `Yükleniyor %${up.busy[0].pct}` : "Görsel veya video yükle"}</span>
          <small>JPG, PNG, MP4, MOV</small>
        </button>
        {value && !library.some((m) => m.url === value.url) && (
          <MediaTile media={value} selected onClick={() => onChange(null)} />
        )}
        {library.map((m) => (
          <MediaTile key={m.url} media={m} selected={value?.url === m.url} onClick={() => onChange(value?.url === m.url ? null : m)} />
        ))}
      </div>
      <UploadProgress busy={up.busy} />
      {up.error && <small className="error-text">{up.error}</small>}
      <span className="hint">
        {hint} Kendi dosyanı yükle ya da ajansAI'da ürettiklerinden seç.
      </span>
    </div>
  );
}

function AdPreview({ placement, media, name, text, headline, cta }: { placement: Placement; media: Media | null; name: string; text: string; headline: string; cta: string }) {
  const visual = media ? (
    media.kind === "image" ? <img src={media.url} alt="" /> : <video src={media.url} muted playsInline autoPlay loop />
  ) : (
    <span>Görsel veya video seç</span>
  );
  const body = text || "Ana metin burada görünür.";

  if (isVertical(placement)) {
    const reels = placement.endsWith("reels");
    return (
      <div className={`ad-phone ${reels ? "reels" : "story"}`}>
        <div className="ad-phone-media">{visual}</div>
        {!reels && <div className="story-bars" aria-hidden="true"><span /></div>}
        <div className="ad-phone-head">
          <span className="ig-avatar" aria-hidden="true" />
          <strong>{name}</strong>
          <small>Sponsorlu</small>
        </div>
        <div className="ad-phone-foot">
          {reels && <p>{body}</p>}
          <span className="ad-phone-cta">{cta}</span>
        </div>
      </div>
    );
  }

  if (placement === "facebook_feed") {
    return (
      <div className="ig-card fb-card">
        <div className="ig-head">
          <span className="ig-avatar fb" aria-hidden="true" />
          <div>
            <strong>{name}</strong>
            <small>Sponsorlu</small>
          </div>
        </div>
        <p className="fb-text">{body}</p>
        <div className="ig-media square">{visual}</div>
        <div className="fb-cta">
          <div>
            <small>{name}</small>
            <strong>{headline || name}</strong>
          </div>
          <span>{cta}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="ig-card">
      <div className="ig-head">
        <span className="ig-avatar" aria-hidden="true" />
        <div>
          <strong>{name}</strong>
          <small>Sponsorlu</small>
        </div>
      </div>
      <div className="ig-media">{visual}</div>
      <div className="ig-cta">
        <span>{cta}</span>
        <Icon name="arrowLeft" size={14} />
      </div>
      <p className="ig-text">
        <strong>{name}</strong> {body}
      </p>
    </div>
  );
}

function MediaTile({ media, selected, onClick }: { media: Media; selected: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`media-tile ${selected ? "selected" : ""}`} onClick={onClick} aria-pressed={selected}>
      {media.kind === "image" ? <img src={media.url} alt="" /> : <video src={media.url} muted playsInline />}
      {media.kind === "video" && <span className="badge">Video</span>}
    </button>
  );
}

/* ---------------- Reklamlarım ---------------- */

function AdList() {
  const [ads, setAds] = useState<AdRow[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const load = () =>
    api<{ ads: AdRow[] }>("/api/ads/meta/ads")
      .then((d) => setAds(d.ads))
      .catch((e) => {
        setError((e as ApiError).message);
        setAds([]);
      });

  useEffect(() => {
    load();
  }, []);

  const act = async (id: string, action: "publish" | "pause") => {
    setBusy(id);
    setError("");
    try {
      await api(`/api/ads/meta/ads/${id}/${action}`, { method: "POST" });
      setConfirmId(null);
      await load();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  };

  if (ads === null) return <EmptyResult loading text="Reklamların ve metrikleri Meta'dan alınıyor…" />;

  return (
    <div>
      {error && <div className="notice error">{error}</div>}
      {ads.length === 0 ? (
        <div className="panel empty">
          <h3>Henüz reklam oluşturmadın</h3>
          <p>"Yeni reklam" sekmesinden ilk Instagram reklamını oluştur; durumu ve sonuçları burada görürsün.</p>
        </div>
      ) : (
        <div className="ad-list">
          {ads.map((ad) => {
            const st = STATUS[ad.status] || { label: ad.status, cls: "pending" };
            const i = ad.insights;
            const active = ad.status === "ACTIVE";
            return (
              <article key={ad.id} className="panel ad-row">
                <div className="ad-thumb">
                  {ad.media_url && (/\.(mp4|mov|webm)(\?|$)/i.test(ad.media_url) ? <video src={ad.media_url} muted playsInline /> : <img src={ad.media_url} alt="" />)}
                </div>
                <div className="ad-main">
                  <div className="ad-title">
                    <strong>{ad.name}</strong>
                    <span className={`status-pill ${st.cls}`}>{st.label}</span>
                  </div>
                  <div className="faint" style={{ fontSize: 13 }}>
                    {OBJECTIVES.find((o) => o.value === ad.objective)?.label} · Günlük {money(ad.daily_budget, ad.currency)} · Instagram
                  </div>
                  {i ? (
                    <div className="ad-metrics">
                      <span>
                        <b>{money(i.spend, ad.currency)}</b> harcama
                      </span>
                      <span>
                        <b>{i.reach.toLocaleString("tr-TR")}</b> erişim
                      </span>
                      <span>
                        <b>{i.impressions.toLocaleString("tr-TR")}</b> gösterim
                      </span>
                      {isMessage(ad.objective) ? (
                        <span>
                          <b>{i.conversations}</b> mesaj
                        </span>
                      ) : (
                        <span>
                          <b>{i.clicks.toLocaleString("tr-TR")}</b> tıklama
                        </span>
                      )}
                      <span>
                        <b>%{i.ctr.toFixed(2)}</b> TO
                      </span>
                    </div>
                  ) : (
                    ad.error && <small className="error-text">{ad.error}</small>
                  )}
                </div>
                <div className="ad-actions">
                  {active ? (
                    <button className="btn btn-ghost btn-sm" disabled={busy === ad.id} onClick={() => act(ad.id, "pause")}>
                      Duraklat
                    </button>
                  ) : confirmId === ad.id ? (
                    <>
                      <span className="faint" style={{ fontSize: 12.5 }}>Harcama başlayacak. Emin misin?</span>
                      <button className="btn btn-primary btn-sm" disabled={busy === ad.id} onClick={() => act(ad.id, "publish")}>
                        Evet, yayına al
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setConfirmId(null)}>
                        Vazgeç
                      </button>
                    </>
                  ) : (
                    <button className="btn btn-primary btn-sm" onClick={() => setConfirmId(ad.id)}>
                      Yayına al
                    </button>
                  )}
                  <a
                    className="btn btn-ghost btn-sm"
                    href={`https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=${ad.ad_account_id}&selected_campaign_ids=${ad.campaign_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Meta'da aç
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
