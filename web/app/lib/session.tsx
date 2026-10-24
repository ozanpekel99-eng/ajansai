"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { Usage, api, getToken } from "./api";

export type User = { id: string; email: string; name: string };

type Session = {
  user: User | null;
  usage: Usage | null;
  metaConnected: boolean;
  /** "manual": Meta API'siz reklam paketi; "api": Meta ile otomatik yayın */
  adsMode: "manual" | "api";
  refresh: () => Promise<void>;
  openCheckout: (planId?: string) => void;
};

const SessionContext = createContext<Session | null>(null);

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession, SessionProvider içinde kullanılmalı");
  return ctx;
}

/** Giriş yapılmamışsa /login'e yönlendirir; kullanıcıyı ve kotayı paylaşır. */
export function SessionProvider({
  children,
  onCheckout,
}: {
  children: React.ReactNode;
  onCheckout: (planId?: string) => void;
}) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [metaConnected, setMetaConnected] = useState(false);
  const [adsMode, setAdsMode] = useState<"manual" | "api">("manual");

  const refresh = useCallback(async () => {
    try {
      const data = await api<{ user: User; usage: Usage }>("/api/auth/me");
      setUser(data.user);
      setUsage(data.usage);
      if (data.usage.ads_enabled) {
        api<{ connected: boolean; mode?: "manual" | "api" }>("/api/ads/meta/status")
          .then((d) => {
            setMetaConnected(d.connected);
            setAdsMode(d.mode === "api" ? "api" : "manual");
          })
          .catch(() => setMetaConnected(false));
      }
    } catch {
      // api() oturum düşmüşse kendisi /login'e yönlendirir
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      // Giriş yapmamış ziyaretçi ücretsiz araçlara gider; oradan üye olabilir.
      window.location.href = "/ucretsiz";
      return;
    }
    setReady(true);
    refresh();
  }, [refresh]);

  if (!ready) return null;

  return (
    <SessionContext.Provider value={{ user, usage, metaConnected, adsMode, refresh, openCheckout: onCheckout }}>
      {children}
    </SessionContext.Provider>
  );
}

function hasChats() {
  try {
    return JSON.parse(localStorage.getItem("ajansai_chats") || "[]").length > 0;
  } catch {
    return false;
  }
}

export function firstName(user: User | null) {
  if (!user) return "";
  return (user.name || user.email.split("@")[0]).split(" ")[0];
}

/** Başlangıç adımları: kenar menü ve ana sayfa aynı listeyi kullanır. */
export function onboardingSteps(usage: Usage | null, metaConnected: boolean, adsMode: "manual" | "api" = "api") {
  const steps = [
    { key: "account", title: "Hesabını oluştur", done: true },
    { key: "idea", title: "İlk sohbetini başlat", done: (!!usage && usage.counts.idea > 0) || hasChats() },
    { key: "plan", title: "Paketini seç", done: !!usage && usage.plan !== "deneme" },
    { key: "meta", title: "Meta reklam hesabını bağla", done: metaConnected },
  ];
  // Reklam paketi modunda Meta bağlantısı gerekmez
  return adsMode === "manual" ? steps.filter((s) => s.key !== "meta") : steps;
}
