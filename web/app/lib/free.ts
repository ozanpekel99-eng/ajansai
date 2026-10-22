"use client";

// Ücretsiz paket: giriş yapmadan da çalışır, kredi harcamaz.

import { useCallback, useEffect, useState } from "react";

import { api } from "./api";

export type FreeStatus = {
  signed_in: boolean;
  chat: { used: number; limit: number; remaining: number };
  images: { used: number; limit: number; remaining: number };
  ai_image_enabled: boolean;
  stock_enabled: boolean;
};

export type StockPhoto = {
  id: number;
  alt: string;
  width: number;
  height: number;
  color: string | null;
  photographer: string;
  photographer_url: string;
  page_url: string;
  thumb: string;
  preview: string;
  download: string;
};

export type StockResult = { photos: StockPhoto[]; page: number; has_more: boolean; source?: string };

export function useFreeStatus() {
  const [status, setStatus] = useState<FreeStatus | null>(null);
  const refresh = useCallback(async () => {
    try {
      setStatus(await api<FreeStatus>("/api/free/status"));
    } catch {
      // durum alınamazsa sayaçlar gösterilmez; işlemler yine sunucuda sınırlanır
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  return { status, setStatus, refresh };
}

/** İndirme bağlantısı (Pexels'te ?dl= ile tarayıcı dosyayı doğrudan kaydeder). */
export function downloadUrl(p: StockPhoto) {
  if (!p.download.includes("pexels.com")) return p.download;
  const sep = p.download.includes("?") ? "&" : "?";
  return `${p.download}${sep}dl=ajansai-pexels-${p.id}.jpg`;
}
