import Link from "next/link";

import { COMPANY, PAYMENT_LOGO_BAND } from "../lib/company";

/**
 * Herkese açık sayfaların sade alt bilgisi: Paketler · Yasal · İletişim ve telif satırı.
 * Sözleşmelerin hepsi /yasal sayfasında toplanır. Ödeme logoları yalnızca `payments` verilen
 * sayfalarda (Paketler) gösterilir; iyzico logoları satın alma yapılan yerde görünür kalır.
 */
export default function SiteFooter({ compact = false, payments = false }: { compact?: boolean; payments?: boolean }) {
  return (
    <footer className={`site-footer ${compact ? "compact" : ""}`}>
      <div className="site-footer-row">
        <nav aria-label="Alt bağlantılar">
          <Link href="/kayit">Paketler</Link>
          <Link href="/yasal">Yasal</Link>
          <Link href="/iletisim">İletişim</Link>
        </nav>
        <span className="site-footer-copy">
          © {new Date().getFullYear()} {COMPANY.brand}
        </span>
      </div>
      {payments &&
        (PAYMENT_LOGO_BAND ? (
          <img className="payment-band" src={PAYMENT_LOGO_BAND} alt="iyzico ile Öde, Visa ve MasterCard" />
        ) : (
          <span className="payment-band-text">iyzico ile Öde · Visa · MasterCard</span>
        ))}
    </footer>
  );
}
