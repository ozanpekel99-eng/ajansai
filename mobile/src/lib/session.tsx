import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, loadToken, saveToken, setUnauthorizedHandler } from "./api";

export type User = { id: string; email: string; name: string };
export type Usage = {
  plan: string;
  plan_name: string;
  period_end: string;
  credits: { total: number; used: number; remaining: number; period_remaining: number; extra: number };
  cycle: string;
  video_enabled: boolean;
  ads_enabled: boolean;
  costs: Record<string, any>;
};

type Session = {
  ready: boolean;
  token: string | null;
  user: User | null;
  usage: Usage | null;
  signIn: (token: string, user: User) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);

  const signOut = useCallback(async () => {
    await saveToken(null);
    setToken(null);
    setUser(null);
    setUsage(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const me = await api<{ user: User; usage: Usage }>("/api/auth/me");
      setUser(me.user);
      setUsage(me.usage);
    } catch {
      // 401 ise oturum kapanır (setUnauthorizedHandler); ağ hatasında eski bilgiler kalır
    }
  }, []);

  const signIn = useCallback(
    async (t: string, u: User) => {
      await saveToken(t);
      setToken(t);
      setUser(u);
      await refresh();
    },
    [refresh],
  );

  useEffect(() => {
    setUnauthorizedHandler(() => void signOut());
    loadToken().then(async (t) => {
      setToken(t);
      if (t) await refresh();
      setReady(true);
    });
    return () => setUnauthorizedHandler(null);
  }, [refresh, signOut]);

  const value = useMemo(() => ({ ready, token, user, usage, signIn, signOut, refresh }), [ready, token, user, usage, signIn, signOut, refresh]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession SessionProvider içinde kullanılmalı");
  return s;
}
