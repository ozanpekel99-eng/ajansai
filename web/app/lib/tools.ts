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
    name: "Sohbet",
    kind: "metin",
    short: "Her şeyi sorabileceğin asistan; yazı, fikir, reklam metni ya da görsel iste.",
    long: "Ne istediğini yaz; form doldurmana gerek yok. Görsel istersen sohbetin içinde üretir. Ürün fotoğrafı eklersen ondan yeni görseller çıkarır; ücretli paketlerde video ve belge de ekleyebilirsin.",
    quota: "ideas",
    costLabel: "Ücretsiz pakette günde 10 mesaj",
    ready: true,
  },
  {
    slug: "gorsel",
    name: "Görsel Üretimi",
    kind: "gorsel",
    short: "Konseptten veya ürün fotoğrafından yüksek kaliteli görsel üret.",
    long: "Yazdığın konsepte göre sosyal medya görseli üretir. Ürün fotoğrafını örnek alabilir; kare, hikâye, gönderi ve yatay formatlar. Ürettiklerin Kütüphane'de birikir.",
    quota: "image",
    costLabel: "Görsel başı 4 kredi",
    ready: true,
  },
  {
    slug: "video",
    name: "Video Üretimi",
    kind: "video",
    short: "Reels ve hikâyeler için 4, 6 ve 8 saniyelik videolar; 720p, 1080p ve 4K.",
    long: "Konsepti kısa videoya dönüştürür: 4, 6 veya 8 saniye; dikey (9:16) ya da yatay (16:9); 720p, 1080p veya 4K. İstersen ürettiğin ya da yüklediğin bir görseli canlandırabilirsin. Üretim genelde 1–2 dakika sürer.",
    quota: "video",
    costLabel: "22 krediden başlar",
    ready: true,
    plan: "Başlangıç",
  },
  {
    slug: "reklam",
    name: "Meta Reklam Kampanyası",
    kind: "reklam",
    short: "Instagram reklamını buradan kur: hesap, kitle, bütçe, görsel/video ve metin; sonuçları izle.",
    long: "Meta hesabını bağla, Instagram\'a özel reklamını adım adım oluştur: amaç, konum ve yaş hedefleme, günlük bütçe, görsel veya video, yapay zeka destekli metin. Reklamı yayınla dediğinde Meta incelemesinden sonra yayına girer; harcama ve sonuçları buradan anlık izlersin.",
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
