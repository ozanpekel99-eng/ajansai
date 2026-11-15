// "Reklam ver" kısayolu: kütüphane ve görsel/video sonuçlarından Reklam aracına dosyayı taşır.
// Bağlantı biçimi (mobil ile aynı): /araclar/reklam?medya=<https url>&tur=gorsel|video&konsept=<kısa açıklama>

export type AdShortcut = { url: string; kind: "image" | "video"; concept: string };

const STORE_KEY = "ajansai_reklam_kisayol";
const CONCEPT_MAX = 200;

/** Reklam aracına giden bağlantı. */
export function adHref(url: string, kind: "image" | "video", concept = ""): string {
  const q = new URLSearchParams({ medya: url, tur: kind === "video" ? "video" : "gorsel" });
  const c = concept.trim().slice(0, CONCEPT_MAX);
  if (c) q.set("konsept", c);
  return `/araclar/reklam?${q.toString()}`;
}

/** Adres satırındaki kısayolu okur; yalnızca https adresleri kabul edilir. */
export function parseAdShortcut(search: string): AdShortcut | null {
  const q = new URLSearchParams(search);
  const url = (q.get("medya") || "").trim();
  if (!/^https:\/\/[^\s]+$/i.test(url)) return null;
  const tur = q.get("tur");
  const kind: "image" | "video" =
    tur === "video" || (tur !== "gorsel" && /\.(mp4|mov|webm)(\?|#|$)/i.test(url)) ? "video" : "image";
  return { url, kind, concept: (q.get("konsept") || "").trim().slice(0, CONCEPT_MAX) };
}

type KV = { getItem(k: string): string | null; setItem(k: string, v: string): void; removeItem(k: string): void };

const store = (): KV | null => {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
};

/** Meta bağlantısı (OAuth yönlendirmesi) sırasında kaybolmasın diye oturumda saklanır. */
export function rememberAdShortcut(s: AdShortcut, kv: KV | null = store()): void {
  try {
    kv?.setItem(STORE_KEY, JSON.stringify(s));
  } catch {
    /* depolama kapalı */
  }
}

/** Önce adres satırı, yoksa oturumda saklanan kısayol (Meta bağlantısından dönüşte). */
export function readAdShortcut(search: string, kv: KV | null = store()): AdShortcut | null {
  const fromUrl = parseAdShortcut(search);
  if (fromUrl) return fromUrl;
  try {
    const raw = kv?.getItem(STORE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<AdShortcut>;
    if (typeof p.url === "string" && /^https:\/\/[^\s]+$/i.test(p.url) && (p.kind === "image" || p.kind === "video")) {
      return { url: p.url, kind: p.kind, concept: typeof p.concept === "string" ? p.concept.slice(0, CONCEPT_MAX) : "" };
    }
  } catch {
    /* bozuk kayıt ya da depolama kapalı */
  }
  return null;
}

/** Dosya reklam formuna eklendikten sonra saklanan kısayol silinir (bir kez kullanılır). */
export function forgetAdShortcut(kv: KV | null = store()): void {
  try {
    kv?.removeItem(STORE_KEY);
  } catch {
    /* depolama kapalı */
  }
}
