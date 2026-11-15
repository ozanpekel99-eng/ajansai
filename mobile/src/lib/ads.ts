// Meta reklam ekranının ortak tipleri ve biçimlendirme yardımcıları (web Reklam.tsx ile aynı uçlar ve etiketler).

export type Objective = "profile" | "traffic" | "whatsapp" | "instagram_dm" | "awareness";

export type Insights = {
  spend: number;
  impressions: number;
  reach: number;
  frequency: number;
  clicks: number;
  link_clicks: number;
  ctr: number;
  cpc: number;
  cpm: number;
  results: number;
  result_label: string;
  cost_per_result: number;
  conversations: number;
  daily: { date: string; spend: number; impressions: number }[];
};

export type AdRow = {
  id: string;
  name: string;
  objective: Objective;
  daily_budget: number;
  budget_type?: "daily" | "lifetime";
  review?: string | null;
  currency: string;
  media_url: string | null;
  status: string;
  insights: Insights | null;
  error?: string;
  campaign_id: string;
  ad_account_id: string;
  created_at: string;
};

export type Range = "today" | "yesterday" | "last_7d" | "last_30d" | "maximum";

export const RANGES: { value: Range; label: string }[] = [
  { value: "today", label: "Bugün" },
  { value: "yesterday", label: "Dün" },
  { value: "last_7d", label: "Son 7 gün" },
  { value: "last_30d", label: "Son 30 gün" },
  { value: "maximum", label: "Tümü" },
];

export const OBJECTIVE_LABELS: Record<Objective, string> = {
  profile: "Trafik (Profil ziyareti)",
  traffic: "Trafik (Web sitesi)",
  whatsapp: "Mesaj (WhatsApp)",
  instagram_dm: "Mesaj (Instagram DM)",
  awareness: "Bilinirlik",
};

export type StatusTone = "ok" | "pending" | "bad";
const STATUS: Record<string, { label: string; tone: StatusTone }> = {
  ACTIVE: { label: "Yayında", tone: "ok" },
  PAUSED: { label: "Duraklatıldı", tone: "pending" },
  CAMPAIGN_PAUSED: { label: "Duraklatıldı", tone: "pending" },
  IN_PROCESS: { label: "İnceleniyor", tone: "pending" },
  PENDING_REVIEW: { label: "Meta incelemesinde", tone: "pending" },
  WITH_ISSUES: { label: "Sorunlu", tone: "bad" },
  DISAPPROVED: { label: "Reddedildi", tone: "bad" },
  DELETED: { label: "Silindi", tone: "bad" },
  ARCHIVED: { label: "Arşivlendi", tone: "pending" },
};

export const statusOf = (s: string) => STATUS[s] ?? { label: s === "UNKNOWN" ? "Bilinmiyor" : s, tone: "pending" as StatusTone };

/** Yayında sayılan (durdurulabilir) durumlar; diğerlerinde "Yayına al" gösterilir. */
export const isRunning = (s: string) => ["ACTIVE", "PENDING_REVIEW", "IN_PROCESS", "WITH_ISSUES"].includes(s);

export const isVideoUrl = (url: string | null) => !!url && /\.(mp4|mov|webm)(\?|$)/i.test(url);

export const money = (n: number, currency = "TRY") => {
  const sym: Record<string, string> = { USD: "$", TRY: "₺", EUR: "€" };
  const val = n.toLocaleString("tr-TR", { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 });
  return `${sym[currency] ?? currency + " "}${val}`;
};

export const num = (v: number, d = 0) => v.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });

export function totals(ads: AdRow[]) {
  const sum = (k: "spend" | "reach" | "impressions" | "results") => ads.reduce((t, a) => t + (a.insights?.[k] || 0), 0);
  return { spend: sum("spend"), results: sum("results"), reach: sum("reach"), impressions: sum("impressions") };
}

export const adsManagerUrl = (ad: Pick<AdRow, "ad_account_id" | "campaign_id">) =>
  `https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=${ad.ad_account_id}&selected_campaign_ids=${ad.campaign_id}`;

/** Meta bağlantısı şimdilik web'den kurulur (OAuth dönüşü web oturumuna bağlı). */
export const WEB_ADS_URL = "https://www.ajansai.tr/araclar/reklam";
