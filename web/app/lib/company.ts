/**
 * Satıcı (şirket) bilgileri: İletişim, Mesafeli Satış Sözleşmesi ve alt bilgi bunları gösterir.
 * Boş bırakılan alan sitede gösterilmez. Adres, güncel vergi levhasındakiyle aynı olmalı (iyzico kontrol eder).
 */
export const COMPANY = {
  brand: "ajansAI",
  legalName: "",
  address: "",
  taxOffice: "",
  taxNumber: "",
  mersis: "",
  phone: "",
  email: "support@ajansai.tr",
  website: "www.ajansai.tr",
};

/** iyzico ile Öde + Visa + MasterCard logo bandı (iyzico resmi logo paketi, beyaz sürüm). */
export const PAYMENT_LOGO_BAND = "";

export const LEGAL_LINKS = [
  { href: "/kayit", label: "Paketler ve fiyatlar" },
  { href: "/kosullar", label: "Kullanım Koşulları" },
  { href: "/gizlilik", label: "Gizlilik Politikası" },
  { href: "/mesafeli-satis-sozlesmesi", label: "Mesafeli Satış Sözleşmesi" },
  { href: "/teslimat-ve-iade", label: "Teslimat ve İade" },
  { href: "/iletisim", label: "İletişim" },
];
