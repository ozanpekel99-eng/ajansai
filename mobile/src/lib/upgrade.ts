// Ücretsiz hak dolunca gösterilen paket kartı ve sohbetteki video önerisi için saf yardımcılar.
// (React/Expo içe aktarmaz; `npm test` ile Node'da doğrudan test edilir.)

/** Kartın neden açıldığı: günlük mesaj, aylık görsel hakkı doldu ya da video paket gerektiriyor. */
export type LimitReason = "chat" | "image" | "video";

export type Plan = {
  id: string;
  name: string;
  price: number;
  currency: string;
  credits: number;
  video_enabled: boolean;
  ads_enabled: boolean;
  examples: { messages: number; images: number; videos: Record<string, number> };
};

export type FreeLimits = { chat_per_day: number; chat_per_day_guest: number; images_per_month: number };
export type Pricing = { plans: Record<string, Plan>; free?: FreeLimits };

/** `/api/free/status` ve ücretsiz sohbet yanıtındaki `free` alanı */
export type FreeStatus = {
  chat: { used: number; limit: number; remaining: number };
  images: { used: number; limit: number; remaining: number };
};

export type VideoSuggestion = { concept: string; aspect: string; duration: number; image_url: string | null; enabled: boolean };

/** Web'deki paket sırası (Başlangıç, Pro, Advanced). */
export const PLAN_ORDER = ["baslangic", "pro", "ajans"];
/** Kartta öne çıkan paket */
export const FEATURED_PLAN = "pro";

export const LIMIT_TITLE: Record<LimitReason, string> = {
  chat: "Bugünkü ücretsiz mesaj hakkın doldu",
  image: "Bu ayki ücretsiz görsel hakkın doldu",
  video: "Video üretimi paketlerle açılır",
};

/** Satın alınabilir paketleri web ile aynı sırada döndürür; bilinmeyen/eksik paketler atlanır. */
export function orderedPlans(pricing: Pricing | null | undefined): Plan[] {
  const plans = pricing?.plans ?? {};
  return PLAN_ORDER.map((id) => plans[id]).filter((p): p is Plan => !!p);
}

/** Sohbet yanıtındaki `limit` alanından kart nedeni (ücretsiz görsel hakkı dolduysa "image"). */
export function limitFromReply(data: { limit?: string | null } | null | undefined): LimitReason | null {
  const l = data?.limit;
  return l === "chat" || l === "image" ? l : null;
}

/** Ücretsiz sohbette 429 = günlük mesaj hakkı doldu. Ücretli sohbetteki hatalar kart açmaz. */
export function limitFromError(status: number, free: boolean): LimitReason | null {
  return free && status === 429 ? "chat" : null;
}

/** Ekranda gösterilecek kart: açıkça tetiklenen neden, yoksa mesaj hakkı bitmiş ücretsiz kullanıcı için "chat". */
export function visibleLimit(reason: LimitReason | null, free: boolean, status: FreeStatus | null | undefined): LimitReason | null {
  if (reason) return reason;
  return free && status && status.chat.remaining <= 0 ? "chat" : null;
}

/** Ücretsiz kullanıcının sohbet altındaki kalan hak metni. */
export function freeFooter(status: FreeStatus | null | undefined): string {
  if (!status) return "Ücretsiz pakettesin";
  return `Bugün ${status.chat.remaining} mesaj, bu ay ${status.images.remaining} görsel hakkın kaldı`;
}

/** Tutarı para birimiyle gösterir: $25, ₺499, €10 (web `money` ile aynı) */
export function money(n: number, currency = "USD"): string {
  const sym: Record<string, string> = { USD: "$", TRY: "₺", EUR: "€" };
  const val = n.toLocaleString("tr-TR", { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 });
  return `${sym[currency] ?? currency + " "}${val}`;
}

export const num = (n: number) => n.toLocaleString("tr-TR");

/** Paket satırındaki özet: "500 kredi · 100 görsel ya da 13 video" */
export function planMeta(p: Plan): string {
  const videos = p.examples?.videos?.["1080p"] ?? 0;
  const parts = [`${num(p.credits)} kredi`, `${num(p.examples?.images ?? 0)} görsel`];
  return videos > 0 ? `${parts[0]} · ${parts[1]} ya da ${num(videos)} video` : parts.join(" · ");
}

/** Video önerisinin alt satırı: "9:16 · 6 sn · görselden başlar" */
export function videoMeta(v: VideoSuggestion): string {
  return `${v.aspect} · ${v.duration} sn${v.image_url ? " · görselden başlar" : ""}`;
}

/** Üret ekranının Video sekmesini öneriyle dolduran yönlendirme parametreleri. */
export function videoRouteParams(v: VideoSuggestion): { tab: "video"; konsept: string; gorsel: string } {
  return { tab: "video", konsept: v.concept, gorsel: v.image_url ?? "" };
}
