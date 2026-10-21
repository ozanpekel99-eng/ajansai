"use client";

import { useEffect, useState } from "react";

import { api } from "./api";

export type Plan = {
  name: string;
  price_try: number;
  price_usd: number;
  video_quota: number;
  image_quota: number;
  ads_enabled: boolean;
};

let cache: Record<string, Plan> | null = null;

export function usePlans() {
  const [plans, setPlans] = useState<Record<string, Plan> | null>(cache);
  useEffect(() => {
    if (cache) return;
    api<{ plans: Record<string, Plan> }>("/api/plans/")
      .then((d) => {
        cache = d.plans;
        setPlans(d.plans);
      })
      .catch(() => setPlans({}));
  }, []);
  return plans;
}

export const tl = (n: number) => `₺${n.toLocaleString("tr-TR")}`;

export const PLAN_ORDER = ["baslangic", "pro", "ajans"];
