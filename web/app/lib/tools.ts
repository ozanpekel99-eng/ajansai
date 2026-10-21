// ajansAI araçları: vitrin, kartlar ve araç sayfaları bu listeden beslenir.
// `ready: false` olanlar "Yakında" olarak gösterilir ve açılamaz.

export type ToolKind = "metin" | "gorsel" | "video" | "reklam";
export type QuotaKind = "ideas" | "image" | "video" | null;

export type Tool = {
  slug: string;
  name: string;
  kind: ToolKind;
  short: string;
  long: string;
  quota: QuotaKind;
  costLabel: string;
  ready: boolean;
  plan?: string; // en az hangi paket gerekiyor (yalnızca bilgi amaçlı)
};

export const KIND_LABEL: Record<ToolKind, string> = {
  metin: "Metin",
  gorsel: "Görsel",
  video: "Video",
  reklam: "Reklam",
};

export const TOOLS: Tool[] = [
  {
    slug: "fikir",
    name: "İçerik Fikri",
    kind: "metin",
    short: "İşletmeni anlat, platforma özel gönderi fikirleri, caption ve hashtag'ler gelsin.",
    long: "İşletme bilgilerine göre Instagram, TikTok ve Facebook için hazır içerik fikirleri üretir. Her fikirde konsept, paylaşıma hazır caption ve hashtag'ler bulunur.",
    quota: "ideas",
    costLabel: "Her 2 fikir 1 kredi",
    ready: true,
  },
  {
    slug: "gorsel",
    name: "Görsel Üretimi",
    kind: "gorsel",
    short: "Konsept metninden gönderiye hazır kare, dikey ve yatay görseller.",
    long: "Yazdığın konsepte göre sosyal medya görseli üretir. Kare, hikâye ve yatay formatları destekler.",
    quota: "image",
    costLabel: "Görsel başı 4 kredi",
    ready: true,
  },
  {
    slug: "video",
    name: "Video Üretimi",
    kind: "video",
    short: "Reels ve hikâyeler için dikey, 5–10 saniyelik kısa videolar.",
    long: "Konsepti dikey kısa videoya dönüştürür. İstersen ürettiğin bir görseli canlandırabilirsin. Üretim genelde 1–3 dakika sürer.",
    quota: "video",
    costLabel: "5 sn 12 kredi · 10 sn 24 kredi",
    ready: true,
    plan: "Başlangıç",
  },
  {
    slug: "reklam",
    name: "Meta Reklam Kampanyası",
    kind: "reklam",
    short: "Meta reklam hesabını bağla, kampanya taslağını buradan oluştur.",
    long: "Kendi Meta reklam hesabını bağlarsın; kampanya taslakları duraklatılmış olarak oluşturulur, sen onaylamadan yayına girmez.",
    quota: null,
    costLabel: "Kredi harcamaz",
    ready: true,
    plan: "Pro",
  },
  {
    slug: "reklam-metni",
    name: "Reklam Metni",
    kind: "metin",
    short: "Meta reklamları için birincil metin, başlık ve açıklama varyasyonları.",
    long: "",
    quota: "ideas",
    costLabel: "Kredi bilgisi yakında",
    ready: false,
  },
  {
    slug: "caption",
    name: "Caption Yazarı",
    kind: "metin",
    short: "Görselini veya konunu yaz, markanın tonunda caption alternatifleri al.",
    long: "",
    quota: "ideas",
    costLabel: "Kredi bilgisi yakında",
    ready: false,
  },
  {
    slug: "hashtag",
    name: "Hashtag Önerisi",
    kind: "metin",
    short: "Şehir, sektör ve ürüne göre karışık hashtag setleri.",
    long: "",
    quota: "ideas",
    costLabel: "Kredi bilgisi yakında",
    ready: false,
  },
  {
    slug: "takvim",
    name: "İçerik Takvimi",
    kind: "metin",
    short: "Bir aylık paylaşım planı: gün, format ve konu başlıklarıyla.",
    long: "",
    quota: "ideas",
    costLabel: "Kredi bilgisi yakında",
    ready: false,
  },
];

export const READY_TOOLS = TOOLS.filter((t) => t.ready);

export function getTool(slug: string) {
  return TOOLS.find((t) => t.slug === slug);
}
