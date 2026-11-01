// "Reklam ver" kısayolu: görsel/video sonuçlarından ve kütüphaneden Reklam aracına dosyayı taşır.
// Bağlantı biçimi web ile aynı (`web/app/lib/adShortcut.ts`):
//   /araclar/reklam?medya=<https url>&tur=gorsel|video&konsept=<kısa açıklama>
// Uygulamadan reklam oluşturma akışı gelene kadar bu bağlantı ajansai.tr'de açılır.

export type AdKind = "image" | "video";

export const WEB_BASE_URL = "https://www.ajansai.tr";
const CONCEPT_MAX = 200;

/** Yalnızca https adresli dosyalar reklama taşınabilir (Meta dosyayı bu adresten çeker). */
export function canAdvertise(url: string | null | undefined): url is string {
  return typeof url === "string" && /^https:\/\/[^\s]+$/i.test(url.trim());
}

/** Reklam aracına giden yol (web ile aynı sorgu biçimi). */
export function adPath(url: string, kind: AdKind, concept = ""): string {
  const q = new URLSearchParams({ medya: url.trim(), tur: kind === "video" ? "video" : "gorsel" });
  const c = concept.trim().replace(/\s+/g, " ").slice(0, CONCEPT_MAX);
  if (c) q.set("konsept", c);
  return `/araclar/reklam?${q.toString()}`;
}

/** ajansai.tr'deki Reklam sayfasının tam adresi. */
export function adWebUrl(url: string, kind: AdKind, concept = "", base = WEB_BASE_URL): string {
  return base.replace(/\/+$/, "") + adPath(url, kind, concept);
}

export type AdAction = { type: "upgrade" } | { type: "open"; url: string } | { type: "invalid" };

/** Düğmeye basınca ne olacağı: paket yoksa paketlere, varsa web'deki reklam sayfasına. */
export function adAction(url: string | null | undefined, kind: AdKind, concept: string, adsEnabled: boolean | undefined): AdAction {
  if (!canAdvertise(url)) return { type: "invalid" };
  if (!adsEnabled) return { type: "upgrade" };
  return { type: "open", url: adWebUrl(url, kind, concept) };
}
