/**
 * Satıcı (şirket) bilgileri: İletişim, Mesafeli Satış Sözleşmesi ve alt bilgi bunları gösterir.
 * Boş bırakılan alan sitede gösterilmez. Adres yalnızca Mesafeli Satış Sözleşmesi'nde gösterilir; iletişim için e-posta.
 */
export const COMPANY = {
  brand: "ajansAI",
  legalName: "Soi Bilişim",
  address: "Kurtköy Mah. Telve Sk. Şehit Murat Erdem No: 2 İç Kapı No: 9, Pendik / İstanbul",
  taxOffice: "Pendik Vergi Dairesi",
  taxNumber: "3040475421",
  mersis: "1455713613600001",
  phone: "",
  email: "support@ajansai.tr",
  website: "www.ajansai.tr",
};

/** iyzico ile Öde + Visa + MasterCard logo bandı (iyzico resmi logo paketi, beyaz sürüm). */
export const PAYMENT_LOGO_BAND = "https://ejoapt623grpxnix.public.blob.vercel-storage.com/site/5eaedd25100b44f0a2859012bb6bf004.bin";

/** /yasal sayfasında listelenen belgeler. */
export const LEGAL_LINKS = [
  { href: "/kosullar", label: "Kullanım Koşulları", desc: "Hizmeti kullanırken geçerli kurallar" },
  { href: "/gizlilik", label: "Gizlilik Politikası", desc: "Hangi verileri neden işlediğimiz, çerezler" },
  { href: "/mesafeli-satis-sozlesmesi", label: "Mesafeli Satış Sözleşmesi", desc: "Paket satın alımları için sözleşme" },
  { href: "/teslimat-ve-iade", label: "Teslimat ve İade", desc: "Paketlerin teslimi, iptal ve iade" },
  { href: "/veri-silme", label: "Verilerini silme", desc: "Hesabını ve verilerini nasıl sildirirsin" },
];
