import Link from "next/link";

export default function LegalPage({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="guest">
      <header className="guest-top">
        <Link href="/ucretsiz">
          <img src="/logo-on-dark.png" alt="ajansAI" />
        </Link>
        <nav className="actions">
          <Link href="/gizlilik" className="btn btn-ghost btn-sm">
            Gizlilik
          </Link>
          <Link href="/kosullar" className="btn btn-ghost btn-sm">
            Koşullar
          </Link>
        </nav>
      </header>
      <main className="page legal">
        <h1>{title}</h1>
        <p className="muted">Son güncelleme: {updated}</p>
        {children}
      </main>
    </div>
  );
}
