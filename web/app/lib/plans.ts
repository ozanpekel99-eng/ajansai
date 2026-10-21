"use client";

import { useEffect, useState } from "react";

import { CreditCosts, api } from "./api";

export type Plan = {
  id: string;
  name: string;
  price_try: number;
  price_usd: number;
  credits: number;
  video_enabled: boolean;
  ads_enabled: boolean;
  /** Bu krediyle yalnızca o işlem yapılırsa kaç tane yapılabileceği */
  examples: { ideas: number; images: number; videos_5: number; videos_10: number };
};

export type Pricing = { plans: Record<string, Plan>; trial: Plan; costs: CreditCosts };

let cache: Pricing | null = null;

/** Paketler ve kredi maliyetleri. Yüklenirken null, hata olursa boş paket listesi. */
export function usePricing() {
  const [data, setData] = useState<Pricing | null>(cache);
  useEffect(() => {
    if (cache) return;
    api<Pricing>("/api/plans/")
      .then((d) => {
        cache = d;
        setData(d);
      })
      .catch(() => setData({ plans: {}, trial: null as unknown as Plan, costs: DEFAULT_COSTS }));
  }, []);
  return data;
}

export function usePlans() {
  return usePricing()?.plans ?? null;
}

export const DEFAULT_COSTS: CreditCosts = { idea_per_2: 1, image: 4, video_5: 12, video_10: 24, ads_draft: 0 };

export const ideaCredits = (count: number, costs: CreditCosts = DEFAULT_COSTS) =>
  Math.max(1, Math.ceil(count / 2)) * costs.idea_per_2;

export const videoCredits = (duration: number, costs: CreditCosts = DEFAULT_COSTS) =>
  duration > 5 ? costs.video_10 : costs.video_5;

export const tl = (n: number) => `₺${n.toLocaleString("tr-TR")}`;
export const num = (n: number) => n.toLocaleString("tr-TR");

export const PLAN_ORDER = ["baslangic", "pro", "ajans"];
