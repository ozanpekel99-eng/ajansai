"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { logout } from "../lib/api";
import { CHATS_EVENT, ChatSummary, deleteChat, listChats } from "../lib/chats";
import { useFreeStatus } from "../lib/free";
import { onboardingSteps, useSession } from "../lib/session";
import Icon from "./Icon";

const MAIN = [
  { href: "/araclar", label: "Araçlar", icon: "grid" },
  { href: "/paketler", label: "Paketler", icon: "tag" },
];

const WORKSPACE = [
  { href: "/araclar/reklam", label: "Reklamlar", icon: "megaphone" },
  { href: "/kullanim", label: "Kullanım", icon: "chart" },
  { href: "/faturalandirma", label: "Faturalandırma", icon: "card" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/" || pathname === "/araclar/fikir";
  if (href === "/araclar") return pathname === "/araclar" || (pathname.startsWith("/araclar/") && pathname !== "/araclar/reklam" && pathname !== "/araclar/fikir");
  return pathname === href || pathname.startsWith(href + "/");
}

export default function Sidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, usage, metaConnected, openCheckout } = useSession();
  const steps = onboardingSteps(usage, metaConnected);
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Ana menü">
      <Link href="/" className="sidebar-logo" onClick={onNavigate}>
        <img src="/logo-on-dark.png" alt="ajansAI" />
      </Link>

      <nav className="nav-group">
        <Link
          href="/?yeni=1"
          className="nav-link new-chat"
          onClick={(e) => {
            e.preventDefault();
            router.push(`/?yeni=${Date.now()}`);
            window.dispatchEvent(new CustomEvent("ajansai:chats", { detail: { activeId: null } }));
            onNavigate();
          }}
        >
          <span className="new-chat-icon">
            <Icon name="plus" size={14} />
          </span>
          Yeni sohbet
        </Link>
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

      <ChatList pathname={pathname} onNavigate={onNavigate} signedIn={!!user} />

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

function activeFromUrl(): string | null {
  if (typeof window === "undefined" || window.location.pathname !== "/") return null;
  return new URLSearchParams(window.location.search).get("c");
}

/** Claude gibi: son sohbetler sol menüde; tıklayınca açılır. */
function ChatList({ pathname, onNavigate, signedIn }: { pathname: string; onNavigate: () => void; signedIn: boolean }) {
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      listChats()
        .then((list) => alive && setChats(list))
        .catch(() => alive && setChats([]));
    load();
    setActive(activeFromUrl());
    const onChange = (e: Event) => {
      const id = (e as CustomEvent).detail?.activeId;
      setActive(id === undefined ? activeFromUrl() : id);
      load();
    };
    window.addEventListener(CHATS_EVENT, onChange);
    return () => {
      alive = false;
      window.removeEventListener(CHATS_EVENT, onChange);
    };
  }, [signedIn]);

  useEffect(() => {
    setActive(activeFromUrl());
  }, [pathname]);

  const remove = async (id: string) => {
    if (!window.confirm("Bu sohbet silinsin mi?")) return;
    await deleteChat(id);
    if (active === id) window.location.href = "/";
  };

  return (
    <div className="chat-list">
      <div className="chat-list-head">
        <span className="nav-heading">Sohbetler</span>
      </div>
      <div className="chat-list-items">
        {chats === null ? null : chats.length === 0 ? (
          <p className="chat-list-empty">Sohbetlerin burada listelenir.</p>
        ) : (
          chats.map((c) => (
            <div key={c.id} className={`chat-item ${active === c.id && pathname === "/" ? "active" : ""}`}>
              <Link href={`/?c=${encodeURIComponent(c.id)}`} title={c.title} onClick={() => { setActive(c.id); onNavigate(); }}>
                {c.title}
              </Link>
              <button type="button" aria-label={`${c.title} sohbetini sil`} onClick={() => remove(c.id)}>
                <Icon name="close" size={12} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
