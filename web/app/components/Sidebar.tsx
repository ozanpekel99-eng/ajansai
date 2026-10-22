"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { logout } from "../lib/api";
import { useFreeStatus } from "../lib/free";
import { onboardingSteps, useSession } from "../lib/session";
import Icon from "./Icon";

const MAIN = [
  { href: "/araclar/fikir", label: "Sohbet", icon: "sparkle" },
  { href: "/", label: "Ana sayfa", icon: "home" },
  { href: "/araclar", label: "Araçlar", icon: "grid" },
  { href: "/paketler", label: "Paketler", icon: "tag" },
];

const WORKSPACE = [
  { href: "/araclar/reklam", label: "Reklamlar", icon: "megaphone" },
  { href: "/kullanim", label: "Kullanım", icon: "chart" },
  { href: "/faturalandirma", label: "Faturalandırma", icon: "card" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/araclar") return pathname === "/araclar" || (pathname.startsWith("/araclar/") && pathname !== "/araclar/reklam" && pathname !== "/araclar/fikir");
  return pathname === href || pathname.startsWith(href + "/");
}

export default function Sidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const pathname = usePathname();
  const { user, usage, metaConnected, openCheckout } = useSession();
  const steps = onboardingSteps(usage, metaConnected);
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Ana menü">
      <Link href="/" className="sidebar-logo" onClick={onNavigate}>
        <img src="/logo-on-dark.png" alt="ajansAI" />
      </Link>

      <nav className="nav-group">
        {MAIN.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`nav-link ${isActive(pathname, item.href) ? "active" : ""}`}
          >
            <Icon name={item.icon} />
            {item.label}
            {item.href === "/paketler" && usage?.plan === "deneme" && <span className="chip chip-indigo">Yükselt</span>}
          </Link>
        ))}
      </nav>

      <div className="nav-heading">Çalışma alanı</div>
      <nav className="nav-group">
        {WORKSPACE.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`nav-link ${isActive(pathname, item.href) ? "active" : ""}`}
          >
            <Icon name={item.icon} />
            {item.label}
            {item.href === "/araclar/reklam" && usage && !usage.ads_enabled && <span className="chip">Pro</span>}
          </Link>
        ))}
        <a className="nav-link" href="mailto:destek@ajansai.tr">
          <Icon name="help" />
          Destek
        </a>
      </nav>

      <div className="sidebar-spacer" />

      {usage && <QuotaCard onUpgrade={() => openCheckout()} />}

      {doneCount < steps.length && (
        <details className="checklist">
          <summary>
            Başlarken <span>{doneCount} / {steps.length}</span>
          </summary>
          {steps.map((s) => (
            <div key={s.key} className={`check-item ${s.done ? "done" : ""}`}>
              <span className="dot" />
              {s.title}
            </div>
          ))}
        </details>
      )}

      {user && (
        <div className="user-row">
          <span className="avatar">{(user.name || user.email)[0].toUpperCase()}</span>
          <div className="who">
            <div>{user.name || user.email.split("@")[0]}</div>
            <div className="email">{user.email}</div>
          </div>
          <button className="icon-btn" onClick={logout} aria-label="Çıkış yap" title="Çıkış yap">
            <Icon name="logout" />
          </button>
        </div>
      )}
    </aside>
  );
}

function FreeQuotaCard({ onUpgrade }: { onUpgrade: () => void }) {
  const { status, refresh } = useFreeStatus();
  const pathname = usePathname();
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 60_000);
    return () => clearInterval(t);
  }, [pathname, refresh]);
  return (
    <div className="quota-card">
      <strong>Ücretsiz paket</strong>
      <div className="meta">
        {status
          ? `Bugün ${status.chat.remaining}/${status.chat.limit} mesaj · ${status.images.remaining}/${status.images.limit} görsel hakkın var`
          : "Günlük mesaj ve aylık görsel hakkı"}
      </div>
      <button className="btn btn-light btn-sm btn-block" onClick={onUpgrade}>
        Paket seç
      </button>
    </div>
  );
}

function QuotaCard({ onUpgrade }: { onUpgrade: () => void }) {
  const { usage } = useSession();
  if (!usage) return null;
  if (usage.plan === "deneme") return <FreeQuotaCard onUpgrade={onUpgrade} />;
  const { total, remaining } = usage.credits;
  const trial = usage.plan === "deneme";
  return (
    <div className="quota-card">
      <strong>{usage.plan_name} paketi</strong>
      <div className="meta">
        {remaining.toLocaleString("tr-TR")} / {total.toLocaleString("tr-TR")} kredin kaldı
      </div>
      <div className="meter" role="progressbar" aria-valuenow={remaining} aria-valuemin={0} aria-valuemax={total}>
        <span style={{ width: `${total ? (remaining / total) * 100 : 0}%` }} />
      </div>
      {trial ? (
        <button className="btn btn-light btn-sm btn-block" onClick={onUpgrade}>
          Paket seç
        </button>
      ) : (
        <Link href="/kullanim" className="btn btn-light btn-sm btn-block">
          Kredi kullanımı
        </Link>
      )}
    </div>
  );
}
