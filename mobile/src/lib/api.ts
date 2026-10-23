// Backend ile konuşan tek yardımcı. Oturum anahtarı cihazda güvenli depoda (SecureStore) saklanır.
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

export const API_URL: string = (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ?? "https://api.ajansai.tr";

const TOKEN_KEY = "ajansai_token";
let memoryToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

export async function loadToken(): Promise<string | null> {
  try {
    memoryToken = Platform.OS === "web" ? globalThis.localStorage?.getItem(TOKEN_KEY) ?? null : await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    memoryToken = null;
  }
  return memoryToken;
}

export async function saveToken(token: string | null) {
  memoryToken = token;
  try {
    if (Platform.OS === "web") {
      if (token) globalThis.localStorage?.setItem(TOKEN_KEY, token);
      else globalThis.localStorage?.removeItem(TOKEN_KEY);
    } else if (token) {
      await SecureStore.setItemAsync(TOKEN_KEY, token);
    } else {
      await SecureStore.deleteItemAsync(TOKEN_KEY);
    }
  } catch {
    // saklanamazsa oturum uygulama kapanana kadar sürer
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** JSON döndüren API çağrısı. Hata durumunda backend'in Türkçe mesajıyla ApiError fırlatır. */
export async function api<T = any>(path: string, options: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (memoryToken) headers.Authorization = `Bearer ${memoryToken}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch {
    throw new ApiError(0, "Sunucuya ulaşılamadı. İnternet bağlantını kontrol edip tekrar dene.");
  }

  let data: any = null;
  try {
    data = await res.json();
  } catch {
    // boş yanıt
  }
  if (!res.ok) {
    if (res.status === 401 && memoryToken) onUnauthorized?.();
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg ?? "İstek geçersiz." : "Bir şeyler ters gitti, tekrar dene.";
    throw new ApiError(res.status, message);
  }
  return data as T;
}
