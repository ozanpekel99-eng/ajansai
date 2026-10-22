"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import ChatPanel from "../components/ChatPanel";
import { FreeImagePanel, StockLibrary } from "../components/FreeTools";
import { getToken } from "../lib/api";
import { useFreeStatus } from "../lib/free";

type Tab = "fikir" | "gorsel" | "stok";

const TABS: { value: Tab; label: string }[] = [
  { value: "fikir", label: "Fikir sohbeti" },
  { value: "gorsel", label: "Ücretsiz görsel" },
  { value: "stok", label: "Stok fotoğraf" },
];

export default function GuestPage() {
  return (
    <Suspense fallback={null}>
      <Guest />
    </Suspense>
  );
}

function Guest() {
  const params = useSearchParams();
  const router = useRouter();
  const { status, setStatus } = useFreeStatus();
  const [signedIn, setSignedIn] = useState(false);
  const tab = (params.get("arac") as Tab) || "fikir";
  const concept = params.get("konsept") || "";

  useEffect(() => setSignedIn(!!getToken()), []);

  const go = (t: Tab, extra = "") => router.push(`/ucretsiz?arac=${t}${extra}`);

  const join = (
    <Link href="/login" className="btn btn-light btn-sm">
      Ücretsiz üye ol
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

      <main className="page">
        <section className="guest-intro">
          <h1>Üye olmadan dene</h1>
          <p>
            Instagram için fikir, caption ve hashtag yazdır; ücretsiz görsel üret ya da telifsiz fotoğraf bul. Kart yok, kayıt
            yok.
            {status && ` Bugün ${status.chat.remaining} mesaj ve 30 günde ${status.images.remaining} görsel hakkın var.`}
          </p>
        </section>

        <div className="mode-row">
          <div className="tabs" role="tablist" aria-label="Araç">
            {TABS.map((t) => (
              <button key={t.value} type="button" role="tab" aria-selected={tab === t.value} className={tab === t.value ? "active" : ""} onClick={() => go(t.value)}>
                {t.label}
              </button>
            ))}
          </div>
          {!signedIn && <span className="hint">Ücretsiz üye olursan günde 20 mesaj yazabilirsin.</span>}
        </div>

        <div hidden={tab !== "fikir"}>
          <ChatPanel
            endpoint="/api/free/chat"
            allowFiles={false}
            conceptHref={(kind, text) => (kind === "gorsel" ? `/ucretsiz?arac=gorsel&konsept=${encodeURIComponent(text)}` : null)}
            onSent={(data) => data?.free && setStatus(data.free)}
            blocker={
              status && status.chat.remaining === 0 ? (
                <div className="notice">
                  <span>Bugünkü {status.chat.limit} ücretsiz mesaj hakkın doldu. Ücretsiz üye olursan günde 20 mesaj yazabilirsin.</span>
                  {!signedIn && join}
                </div>
              ) : undefined
            }
            footer={() =>
              status ? `Ücretsiz · bugün ${status.chat.remaining}/${status.chat.limit} mesaj hakkın var · Enter gönderir` : "Ücretsiz · Enter gönderir"
            }
          />
        </div>

        {tab === "gorsel" && (
          <FreeImagePanel key={concept} status={status} onStatus={setStatus} initialConcept={concept} upsell={!signedIn ? join : undefined} />
        )}

        {tab === "stok" && <StockLibrary enabled={status ? status.stock_enabled : true} />}
      </main>
    </div>
  );
}
