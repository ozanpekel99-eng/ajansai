"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { Usage, api, getToken } from "./api";

export type User = { id: string; email: string; name: string };

type Session = {
  user: User | null;
  usage: Usage | null;
  metaConnected: boolean;
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

  const refresh = useCallback(async () => {
    try {
      const data = await api<{ user: User; usage: Usage }>("/api/auth/me");
      setUser(data.user);
      setUsage(data.usage);
      if (data.usage.ads_enabled) {
        api<{ connected: boolean }>("/api/ads/meta/status")
          .then((d) => setMetaConnected(d.connected))
          .catch(() => setMetaConnected(false));
      }
    } catch {
      // api() oturum düşmüşse kendisi /login'e yönlendirir
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    setReady(true);
    refresh();
  }, [refresh]);

  if (!ready) return null;

  return (
    <SessionContext.Provider value={{ user, usage, metaConnected, refresh, openCheckout: onCheckout }}>
      {children}
    </SessionContext.Provider>
  );
}

export function firstName(user: User | null) {
  if (!user) return "";
  return (user.name || user.email.split("@")[0]).split(" ")[0];
}

/** Başlangıç adımları: kenar menü ve ana sayfa aynı listeyi kullanır. */
export function onboardingSteps(usage: Usage | null, metaConnected: boolean) {
  return [
    { key: "account", title: "Hesabını oluştur", done: true },
    { key: "idea", title: "İlk içerik fikrini üret", done: !!usage && usage.counts.idea > 0 },
    { key: "plan", title: "Paketini seç", done: !!usage && usage.plan !== "deneme" },
    { key: "meta", title: "Meta reklam hesabını bağla", done: metaConnected },
  ];
}
