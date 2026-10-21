"use client";

import { put } from "@vercel/blob/client";

import { api } from "./api";

export type UploadKind = "image" | "video" | "document";

export type Uploaded = {
  url: string;
  content_type: string;
  name: string;
  kind: UploadKind;
};

export const ACCEPT: Record<UploadKind, string> = {
  image: "image/jpeg,image/png,image/webp",
  video: "video/mp4,video/quicktime,video/webm",
  document:
    "application/pdf,text/plain,text/csv,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

/** Dosyayı tarayıcıdan doğrudan depoya yükler (büyük videolar backend'den geçmez). */
export async function uploadFile(file: File, onProgress?: (pct: number) => void): Promise<Uploaded> {
  const contentType = file.type || "application/octet-stream";
  const { client_token, pathname, kind } = await api<{ client_token: string; pathname: string; kind: UploadKind }>(
    "/api/uploads/token",
    { method: "POST", body: JSON.stringify({ filename: file.name, content_type: contentType, size: file.size }) },
  );
  const blob = await put(pathname, file, {
    access: "public",
    token: client_token,
    contentType,
    multipart: file.size > 8 * 1024 * 1024,
    onUploadProgress: onProgress ? (e) => onProgress(Math.round(e.percentage)) : undefined,
  });
  return { url: blob.url, content_type: contentType, name: file.name, kind };
}
