"use client";

import { useCallback, useEffect, useState } from "react";

import { Usage, api, getToken } from "./api";

/** Giriş yapılmamışsa /login'e yönlendirir; giriş varsa kullanım bilgisini getirir. */
export function useAuth() {
  const [ready, setReady] = useState(false);
  const [usage, setUsage] = useState<Usage | null>(null);

  const refreshUsage = useCallback(async () => {
    try {
      setUsage(await api<Usage>("/api/plans/usage"));
    } catch {
      // Kullanım bilgisi gösterilemese de sayfa çalışmaya devam eder
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    setReady(true);
    refreshUsage();
  }, [refreshUsage]);

  return { ready, usage, refreshUsage };
}
