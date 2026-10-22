"use client";

import { useEffect, useState } from "react";

import { CreditCosts, VideoDuration, VideoResolution, api } from "./api";

export type Plan = {
  id: string;
  name: string;
  price: number;
  currency: string;
  /** KDV hariç yıllık fiyat (%20 indirimli) */
  price_yearly: number;
  yearly_discount: number;
  vat_rate: number;
  credits: number;
  video_enabled: boolean;
  ads_enabled: boolean;
  /** Bu krediyle yalnızca o işlem yapılırsa kaç tane yapılabileceği */
  examples: { messages: number; images: number; videos: Record<VideoResolution, number> };
};

export type FreeLimits = { chat_per_day: number; chat_per_day_guest: number; images_per_month: number };
export type Pricing = { plans: Record<string, Plan>; trial: Plan; costs: CreditCosts; free?: FreeLimits };

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
  chat_message: 1,
  chat_attachment: 1,
  chat_pdf_pages: 10,
  describe: 1,
  image: 4,
  ads_draft: 0,
  video: {
    "720p": { "4": 8, "6": 12, "8": 16 },
    "1080p": { "4": 25, "6": 36, "8": 48 },
    "4k": { "4": 72, "6": 108, "8": 144 },
  },
  video_audio: {
    "720p": { "4": 12, "6": 18, "8": 24 },
    "1080p": { "4": 36, "6": 54, "8": 72 },
    "4k": { "4": 84, "6": 126, "8": 168 },
  },
};

export const VIDEO_DURATIONS: VideoDuration[] = [4, 6, 8];
export const VIDEO_RESOLUTIONS: { value: VideoResolution; label: string }[] = [
  { value: "720p", label: "Standart 720p" },
  { value: "1080p", label: "Yüksek kalite 1080p" },
  { value: "4k", label: "4K" },
];

export const ideaCredits = (count: number, costs: CreditCosts = DEFAULT_COSTS) =>
  Math.max(1, Math.ceil(count / 2)) * costs.idea_per_2;

export const videoCredits = (
  duration: VideoDuration,
  resolution: VideoResolution = "720p",
  costs: CreditCosts = DEFAULT_COSTS,
  audio = false,
) => (audio ? costs.video_audio ?? DEFAULT_COSTS.video_audio : costs.video)[resolution][String(duration)];

export const tl = (n: number) => `₺${n.toLocaleString("tr-TR")}`;

/** Tutarı para birimiyle gösterir: $25, ₺499, €10 */
export const money = (n: number, currency = "USD") => {
  const sym: Record<string, string> = { USD: "$", TRY: "₺", EUR: "€" };
  const val = n.toLocaleString("tr-TR", { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 });
  return `${sym[currency] ?? currency + " "}${val}`;
};
export const num = (n: number) => n.toLocaleString("tr-TR");

export const PLAN_ORDER = ["baslangic", "pro", "ajans"];

/** Kayıtta seçilen ücretli paket: kayıttan sonra panelde ödeme penceresi bununla açılır. */
export const PENDING_PLAN_KEY = "ajansai_signup_plan";

export type Cycle = "monthly" | "yearly";

/** KDV hariç dönem fiyatı. */
export function cyclePrice(p: Plan, cycle: Cycle) {
  return cycle === "yearly" ? p.price_yearly : p.price;
}

/** Yıllık pakette aylık karşılığı. */
export function perMonth(p: Plan, cycle: Cycle) {
  return cycle === "yearly" ? Math.round((p.price_yearly / 12) * 100) / 100 : p.price;
}
