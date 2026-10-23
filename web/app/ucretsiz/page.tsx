"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ChatPanel from "../components/ChatPanel";
import SiteFooter from "../components/SiteFooter";
import UpgradeCard from "../components/UpgradeCard";
import { getToken } from "../lib/api";
import { useFreeStatus } from "../lib/free";
import { PENDING_PLAN_KEY } from "../lib/plans";

/** Giriş yapmış kullanıcı: panelde ödeme penceresi bu paketle açılır. */
function openPlan(id: string) {
  try {
    localStorage.setItem(PENDING_PLAN_KEY, id);
  } catch {
    // depolama kapalı: panelde paket yeniden seçilir
  }
  window.location.href = "/paketler";
}

/** Üye olmadan dene: ChatGPT gibi tek sohbet; görsel de sohbetten istenir. */
export default function GuestPage() {
  const { status, setStatus } = useFreeStatus();
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    setSignedIn(!!getToken());
  }, []);

  const join = (
    <Link href="/kayit" className="btn btn-light btn-sm">
      Üye ol
    </Link>
  );

  return (
    <div className="guest">
      <header className="guest-top">
        <Link href="/ucretsiz">
          <img src="/logo-on-dark.png" alt="ajansAI" />
        </Link>
        <div className="actions">
          {signedIn ? (
            <Link href="/" className="btn btn-light btn-sm">
              Panele git
            </Link>
          ) : (
            <>
              <Link href="/login" className="btn btn-ghost btn-sm">
                Giriş yap
              </Link>
              {join}
            </>
          )}
        </div>
      </header>

      <main className="page guest-main">
        <ChatPanel
          endpoint="/api/free/chat"
          attach="basic"
          tools={{
            video: { href: "/kayit", locked: "Paketle açılır" },
            ads: { href: "/kayit", locked: "Pro paketle açılır" },
          }}
          onSent={(data) => data?.free && setStatus(data.free)}
          upgrade={(reason) => <UpgradeCard reason={reason} onPick={signedIn ? openPlan : undefined} />}
          blocker={
            status && status.chat.remaining === 0 ? (
              <div className="notice">
                <span>Bugünkü {status.chat.limit} ücretsiz mesaj hakkın doldu. Üye olursan günde 10 mesaj yazabilirsin.</span>
                {!signedIn && join}
              </div>
            ) : undefined
          }
          footer={() => (status ? `Bugün ${status.chat.remaining} mesaj hakkın kaldı` : "")}
        />
      </main>
      <SiteFooter compact />
    </div>
  );
}
