/**
 * Satıcı (şirket) bilgileri: İletişim, Mesafeli Satış Sözleşmesi ve alt bilgi bunları gösterir.
 * Boş bırakılan alan sitede gösterilmez. Adres, güncel vergi levhasındakiyle aynı olmalı (iyzico kontrol eder).
 */
export const COMPANY = {
  brand: "ajansAI",
  legalName: "İlayda Pekel",
  address: "",
  taxOffice: "Pendik Vergi Dairesi",
  taxNumber: "",
  mersis: "",
  phone: "",
  email: "support@ajansai.tr",
  website: "www.ajansai.tr",
};

/** iyzico ile Öde + Visa + MasterCard logo bandı (iyzico resmi logo paketi, beyaz sürüm). */
export const PAYMENT_LOGO_BAND = "https://ejoapt623grpxnix.public.blob.vercel-storage.com/site/5eaedd25100b44f0a2859012bb6bf004.bin";

export const LEGAL_LINKS = [
  { href: "/kayit", label: "Paketler ve fiyatlar" },
  { href: "/kosullar", label: "Kullanım Koşulları" },
  { href: "/gizlilik", label: "Gizlilik Politikası" },
  { href: "/mesafeli-satis-sozlesmesi", label: "Mesafeli Satış Sözleşmesi" },
  { href: "/teslimat-ve-iade", label: "Teslimat ve İade" },
  { href: "/iletisim", label: "İletişim" },
];
