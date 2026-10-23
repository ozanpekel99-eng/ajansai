import Link from "next/link";

import SiteFooter from "./SiteFooter";

export default function LegalPage({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="guest">
      <header className="guest-top">
        <Link href="/ucretsiz">
          <img src="/logo-on-dark.png" alt="ajansAI" />
        </Link>
        <nav className="actions">
          <Link href="/yasal" className="btn btn-ghost btn-sm">
            Yasal
          </Link>
          <Link href="/iletisim" className="btn btn-ghost btn-sm">
            İletişim
          </Link>
        </nav>
      </header>
      <main className="page legal">
        <h1>{title}</h1>
        <p className="muted">Son güncelleme: {updated}</p>
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
