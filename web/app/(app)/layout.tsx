"use client";

import { useCallback, useState } from "react";
import Link from "next/link";

import CheckoutModal from "../components/CheckoutModal";
import Icon from "../components/Icon";
import Sidebar from "../components/Sidebar";
import { SessionProvider, useSession } from "../lib/session";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [checkout, setCheckout] = useState<{ open: boolean; plan?: string }>({ open: false });
  const openCheckout = useCallback((plan?: string) => setCheckout({ open: true, plan }), []);

  return (
    <SessionProvider onCheckout={openCheckout}>
      <Shell>{children}</Shell>
      {checkout.open && <Checkout plan={checkout.plan} onClose={() => setCheckout({ open: false })} />}
    </SessionProvider>
  );
}

function Checkout({ plan, onClose }: { plan?: string; onClose: () => void }) {
  const { usage } = useSession();
  return <CheckoutModal initialPlan={plan} currentPlan={usage?.plan} onClose={onClose} />;
}

function Shell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="shell">
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} />}
      <div className="main">
        <header className="topbar">
          <Link href="/">
            <img src="/logo-on-dark.png" alt="ajansAI" />
          </Link>
          <button className="icon-btn" onClick={() => setMenuOpen(true)} aria-label="Menüyü aç">
            <Icon name="menu" />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
