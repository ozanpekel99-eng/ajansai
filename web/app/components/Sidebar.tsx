"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { logout } from "../lib/api";
import { onboardingSteps, useSession } from "../lib/session";
import Icon from "./Icon";

const MAIN = [
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
  if (href === "/araclar") return pathname === "/araclar" || (pathname.startsWith("/araclar/") && pathname !== "/araclar/reklam");
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

function QuotaCard({ onUpgrade }: { onUpgrade: () => void }) {
  const { usage } = useSession();
  if (!usage) return null;

  if (usage.plan === "deneme") {
    const quota = usage.ideas.quota || 0;
    const used = Math.min(usage.ideas.used, quota);
    return (
      <div className="quota-card">
        <strong>Deneme paketi</strong>
        <div className="meta">
          Bu ay {quota - used} / {quota} fikir hakkın kaldı
        </div>
        <div className="meter">
          <span style={{ width: `${quota ? ((quota - used) / quota) * 100 : 0}%` }} />
        </div>
        <button className="btn btn-light btn-sm btn-block" onClick={onUpgrade}>
          Paket seç
        </button>
      </div>
    );
  }

  const left = usage.video.quota - usage.video.used;
  return (
    <div className="quota-card">
      <strong>{usage.plan_name} paketi</strong>
      <div className="meta">
        {left} video, {usage.image.quota - usage.image.used} görsel hakkın kaldı
      </div>
      <div className="meter">
        <span style={{ width: `${usage.video.quota ? (left / usage.video.quota) * 100 : 0}%` }} />
      </div>
      <Link href="/faturalandirma" className="btn btn-light btn-sm btn-block">
        Paketi yönet
      </Link>
    </div>
  );
}
