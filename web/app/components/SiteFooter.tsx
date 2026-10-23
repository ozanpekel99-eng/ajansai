import Link from "next/link";

import { COMPANY, LEGAL_LINKS, PAYMENT_LOGO_BAND } from "../lib/company";

/** Herkese açık sayfaların alt bilgisi: yasal bağlantılar, iletişim ve ödeme logoları. */
export default function SiteFooter({ compact = false }: { compact?: boolean }) {
  return (
    <footer className={`site-footer ${compact ? "compact" : ""}`}>
      <nav aria-label="Yasal bağlantılar">
        {LEGAL_LINKS.map((l) => (
          <Link key={l.href} href={l.href}>
            {l.label}
          </Link>
        ))}
      </nav>
      <div className="site-footer-row">
        <span className="site-footer-contact">
          <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a>
          {COMPANY.phone && (
            <>
              {" · "}
              <a href={`tel:${COMPANY.phone.replace(/\s/g, "")}`}>{COMPANY.phone}</a>
            </>
          )}
          {" · "}© {new Date().getFullYear()} {COMPANY.legalName || COMPANY.brand}
        </span>
        {PAYMENT_LOGO_BAND ? (
          <img className="payment-band" src={PAYMENT_LOGO_BAND} alt="iyzico ile Öde, Visa ve MasterCard" />
        ) : (
          <span className="payment-band-text">iyzico ile Öde · Visa · MasterCard</span>
        )}
      </div>
    </footer>
  );
}
