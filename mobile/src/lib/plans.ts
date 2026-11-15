import { useEffect, useState } from "react";

import { api } from "./api";
import type { Pricing } from "./upgrade";

let cache: Pricing | null = null;

/** Paketler (`/api/plans/`, web ile aynı uç). Yüklenirken null, hata olursa boş paket listesi. */
export function usePricing(): Pricing | null {
  const [data, setData] = useState<Pricing | null>(cache);
  useEffect(() => {
    if (cache) return;
    let alive = true;
    api<Pricing>("/api/plans/")
      .then((d) => {
        cache = d;
        if (alive) setData(d);
      })
      .catch(() => alive && setData({ plans: {} }));
    return () => {
      alive = false;
    };
  }, []);
  return data;
}
