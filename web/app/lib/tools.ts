// ajansAI araçları: vitrin, kartlar ve araç sayfaları bu listeden beslenir.

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
    short: "ChatGPT gibi yaz: fikir, caption, hashtag ve reklam metni. Fotoğraf, video ve belge ekleyebilirsin.",
    long: "Ne istediğini yaz; form doldurmana gerek yok. Ürün fotoğrafı, örnek video veya katalog eklersen onlara bakarak fikir, caption, hashtag ve reklam metni üretir.",
    quota: "ideas",
    costLabel: "Mesaj başı 1 kredi",
    ready: true,
  },
  {
    slug: "gorsel",
    name: "Görsel Üretimi",
    kind: "gorsel",
    short: "Konseptten veya kendi ürün fotoğrafından gönderiye hazır görseller.",
    long: "Yazdığın konsepte göre sosyal medya görseli üretir. Kendi ürün fotoğrafını veya beğendiğin bir örneği yüklersen onu örnek alır. Kare, hikâye, gönderi ve yatay formatlar.",
    quota: "image",
    costLabel: "Görsel başı 4 kredi",
    ready: true,
  },
  {
    slug: "video",
    name: "Video Üretimi",
    kind: "video",
    short: "Reels ve hikâyeler için 5, 7 ve 10 saniyelik dikey videolar; 720p, 1080p ve 4K.",
    long: "Konsepti dikey kısa videoya dönüştürür: 5, 7 veya 10 saniye; 720p, 1080p veya 4K. İstersen ürettiğin bir görseli canlandırabilirsin. Üretim genelde 1–3 dakika sürer.",
    quota: "video",
    costLabel: "12 krediden başlar",
    ready: true,
    plan: "Başlangıç",
  },
  {
    slug: "reklam",
    name: "Meta Reklam Kampanyası",
    kind: "reklam",
    short: "Instagram reklamını buradan kur: hesap, kitle, bütçe, görsel/video ve metin; sonuçları izle.",
    long: "Meta hesabını bağla, Instagram\'a özel reklamını adım adım oluştur: amaç, konum ve yaş hedefleme, günlük bütçe, görsel veya video, yapay zeka destekli metin. Reklam duraklatılmış oluşur; Yayına al dediğinde başlar, harcama ve sonuçları buradan izlersin.",
    quota: null,
    costLabel: "Kredi harcamaz",
    ready: true,
    plan: "Pro",
  },
];

export const READY_TOOLS = TOOLS.filter((t) => t.ready);

export function getTool(slug: string) {
  return TOOLS.find((t) => t.slug === slug);
}
