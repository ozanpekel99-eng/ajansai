// Fotoğraf/video/belge yükleme: backend'den tek seferlik yükleme izni alınır, dosya doğrudan depoya gider.
import { put } from "@vercel/blob/client";
import * as ImagePicker from "expo-image-picker";

import { api } from "./api";

export type Uploaded = { url: string; content_type: string; name: string; kind: "image" | "video" | "document" };

export async function uploadUri(uri: string, name: string, contentType: string, onProgress?: (pct: number) => void): Promise<Uploaded> {
  const file = await (await fetch(uri)).blob();
  const { client_token, pathname, kind } = await api<{ client_token: string; pathname: string; kind: Uploaded["kind"] }>("/api/uploads/token", {
    body: { filename: name, content_type: contentType, size: file.size },
  });
  const blob = await put(pathname, file, {
    access: "public",
    token: client_token,
    contentType,
    multipart: file.size > 8 * 1024 * 1024,
    onUploadProgress: onProgress ? (e) => onProgress(Math.round(e.percentage)) : undefined,
  });
  return { url: blob.url, content_type: contentType, name, kind };
}

/** Galeriden görsel (veya video) seçtirir; iptal edilirse boş liste döner. */
export async function pickMedia(opts: { video?: boolean; multiple?: number } = {}): Promise<ImagePicker.ImagePickerAsset[]> {
  const res = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: opts.video ? ["images", "videos"] : ["images"],
    allowsMultipleSelection: (opts.multiple ?? 1) > 1,
    selectionLimit: opts.multiple ?? 1,
    quality: 0.9,
  });
  return res.canceled ? [] : res.assets;
}

export async function takePhoto(): Promise<ImagePicker.ImagePickerAsset[]> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) return [];
  const res = await ImagePicker.launchCameraAsync({ quality: 0.9 });
  return res.canceled ? [] : res.assets;
}

export function assetMeta(a: ImagePicker.ImagePickerAsset): { name: string; type: string } {
  const type = a.mimeType || (a.type === "video" ? "video/mp4" : "image/jpeg");
  const ext = type.split("/")[1] || "jpg";
  return { name: a.fileName || `${a.type === "video" ? "video" : "foto"}-${Date.now()}.${ext}`, type };
}
