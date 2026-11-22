// @ajansai.tr yayın kuyruğu (yönetici) için saf yardımcılar. Backend uçları:
// /api/admin/social/import, /queue, /{id}/approve, /{id}/skip, PUT /{id}.
// Saatler İstanbul saatidir; backend "YYYY-AA-GG SS:DD" biçimini kullanır.

export type SocialStatus = "pending" | "approved" | "skipped" | "published" | "failed";
export type SocialKind = "image" | "carousel" | "reels";

export type SocialPost = {
  id: string;
  week: string;
  idx: number;
  kind: SocialKind;
  title: string;
  target: string;
  caption: string;
  media: string[];
  scheduled_at: string;
  scheduled_local: string;
  status: SocialStatus | string;
  ig_media_id: string | null;
  error: string | null;
  approved_by: string | null;
  problems: string[];
};

export type ImportResult = { week: string; created: number; updated: number; kept: number; warnings: string[] };

export const CAPTION_MAX = 2200;
export const HASHTAG_MAX = 30;

export const STATUS_LABEL: Record<string, { text: string; tone: "pending" | "success" | "failure" | "" }> = {
  pending: { text: "Onay bekliyor", tone: "pending" },
  approved: { text: "Onaylandı", tone: "success" },
  skipped: { text: "Atlandı", tone: "" },
  published: { text: "Paylaşıldı", tone: "success" },
  failed: { text: "Paylaşılamadı", tone: "failure" },
};

export const KIND_LABEL: Record<string, string> = { image: "Gönderi", carousel: "Carousel", reels: "Reels" };

export function statusLabel(status: string) {
  return STATUS_LABEL[status] || { text: status, tone: "" as const };
}

const pad = (n: number) => String(n).padStart(2, "0");
const ymd = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** Verilen günden sonraki (bugün pazartesiyse bugün) pazartesi, YYYY-AA-GG. */
export function upcomingMonday(from: Date = new Date()): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const add = (8 - d.getDay()) % 7; // pazar=0 → 1, pazartesi=1 → 0
  d.setDate(d.getDate() + add);
  return ymd(d);
}

/** Backend "YYYY-AA-GG SS:DD" → <input type="datetime-local"> değeri. */
export function toInputValue(local: string): string {
  return (local || "").trim().replace(" ", "T").slice(0, 16);
}

/** <input type="datetime-local"> değeri → backend "YYYY-AA-GG SS:DD". Geçersizse null. */
export function fromInputValue(value: string): string | null {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec((value || "").trim());
  return m ? `${m[1]} ${m[2]}` : null;
}

const DAYS = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

/** "2026-11-24 12:30" → "Salı 24 Kasım, 12:30" (saat dilimi dönüşümü yapmaz; değer zaten İstanbul saati). */
export function formatLocal(local: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(local || "");
  if (!m) return local;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}, ${m[4]}`;
}

/** "2026-11-23" → "23 Kasım 2026 haftası" */
export function weekLabel(week: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(week || "");
  if (!m) return week;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]} haftası`;
}

export function hashtagCount(caption: string): number {
  return (caption.match(/#[\p{L}\p{N}_]+/gu) || []).length;
}

/** Açıklama için anlık uyarılar (backend aynı kuralları onayda da uygular). */
export function captionWarnings(caption: string): string[] {
  const out: string[] = [];
  if (!caption.trim()) out.push("Açıklama boş.");
  if (caption.length > CAPTION_MAX) out.push(`Açıklama ${CAPTION_MAX} karakteri aşıyor (${caption.length}).`);
  const tags = hashtagCount(caption);
  if (tags > HASHTAG_MAX) out.push(`En fazla ${HASHTAG_MAX} etiket olabilir (${tags}).`);
  return out;
}

export function isVideo(url: string): boolean {
  return /\.(mp4|mov)$/i.test(url.split("?")[0]);
}

/** Haftalara göre grupla; en yeni hafta önce, hafta içinde planlı zamana göre. */
export function groupByWeek(posts: SocialPost[]): { week: string; posts: SocialPost[] }[] {
  const map = new Map<string, SocialPost[]>();
  for (const p of posts) {
    if (!map.has(p.week)) map.set(p.week, []);
    map.get(p.week)!.push(p);
  }
  return [...map.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0))
    .map(([week, list]) => ({
      week,
      posts: [...list].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at) || a.idx - b.idx),
    }));
}

export function countByStatus(posts: SocialPost[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const p of posts) out[p.status] = (out[p.status] || 0) + 1;
  return out;
}

/** plan.json metnini okur. Hata durumunda Türkçe mesajla Error fırlatır. */
export function parsePlan(text: string): Record<string, unknown>[] {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("plan.json okunamadı: geçerli bir JSON değil.");
  }
  if (data && typeof data === "object" && !Array.isArray(data) && Array.isArray((data as { posts?: unknown }).posts)) {
    data = (data as { posts: unknown[] }).posts;
  }
  if (!Array.isArray(data) || data.length === 0) throw new Error("plan.json bir gönderi listesi olmalı.");
  if (data.length > 40) throw new Error("Bir haftada en fazla 40 gönderi aktarılabilir.");
  data.forEach((p, i) => {
    if (!p || typeof p !== "object" || Array.isArray(p)) throw new Error(`${i + 1}. satır bir nesne olmalı.`);
    const row = p as Record<string, unknown>;
    for (const key of ["day", "time", "caption"]) {
      if (typeof row[key] !== "string" || !(row[key] as string).trim()) throw new Error(`${i + 1}. satırda '${key}' eksik.`);
    }
    if (!Array.isArray(row.files) || row.files.length === 0) throw new Error(`${i + 1}. satırda dosya listesi ('files') eksik.`);
  });
  return data as Record<string, unknown>[];
}

/** Dosya adı plan.json yolundan haftayı çıkarır: ".../2026-11-23/plan.json" → "2026-11-23". */
export function weekFromPath(path: string): string | null {
  const m = /(\d{4}-\d{2}-\d{2})(?=[\\/][^\\/]*$)/.exec(path || "");
  return m ? m[1] : null;
}

/** Görselin/videoların önüne eklenecek herkese açık adres; boş bırakılabilir (tam https adresi plan.json'daysa). */
export function normalizeMediaBase(value: string): { value: string | null; error?: string } {
  const v = (value || "").trim();
  if (!v) return { value: null };
  if (!/^https:\/\/\S+$/.test(v)) return { value: null, error: "Dosya adresi https:// ile başlamalı." };
  return { value: v.replace(/\/+$/, "") };
}
