"use client";

import { useEffect, useState } from "react";

import { CreditCosts, VideoDuration, VideoResolution, api } from "./api";

export type Plan = {
  id: string;
  name: string;
  price_try: number;
  price_usd: number;
  credits: number;
  video_enabled: boolean;
  ads_enabled: boolean;
  /** Bu krediyle yalnızca o işlem yapılırsa kaç tane yapılabileceği */
  examples: { ideas: number; images: number; videos: Record<VideoResolution, number> };
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

export const DEFAULT_COSTS: CreditCosts = {
  idea_per_2: 1,
  image: 4,
  ads_draft: 0,
  video: {
    "720p": { "5": 12, "7": 17, "10": 24 },
    "1080p": { "5": 27, "7": 37, "10": 53 },
    "4k": { "5": 355, "7": 495, "10": 710 },
  },
};

export const VIDEO_DURATIONS: VideoDuration[] = [5, 7, 10];
export const VIDEO_RESOLUTIONS: { value: VideoResolution; label: string }[] = [
  { value: "720p", label: "720p" },
  { value: "1080p", label: "1080p" },
  { value: "4k", label: "4K" },
];

export const ideaCredits = (count: number, costs: CreditCosts = DEFAULT_COSTS) =>
  Math.max(1, Math.ceil(count / 2)) * costs.idea_per_2;

export const videoCredits = (duration: VideoDuration, resolution: VideoResolution = "720p", costs: CreditCosts = DEFAULT_COSTS) =>
  costs.video[resolution][String(duration)];

export const tl = (n: number) => `₺${n.toLocaleString("tr-TR")}`;
export const num = (n: number) => n.toLocaleString("tr-TR");

export const PLAN_ORDER = ["baslangic", "pro", "ajans"];
