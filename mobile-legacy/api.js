import AsyncStorage from "@react-native-async-storage/async-storage";

import { API_URL } from "./config";

const TOKEN_KEY = "ajansai_token";
let cachedToken = null;
let onLogout = null;

export async function loadToken() {
  cachedToken = await AsyncStorage.getItem(TOKEN_KEY);
  return cachedToken;
}

export async function saveToken(token) {
  cachedToken = token;
  await AsyncStorage.setItem(TOKEN_KEY, token);
}

export async function clearToken() {
  cachedToken = null;
  await AsyncStorage.removeItem(TOKEN_KEY);
}

/** Oturum düştüğünde (401) çağrılacak fonksiyon; App.js giriş ekranına döner. */
export function setLogoutHandler(fn) {
  onLogout = fn;
}

export async function api(path, options = {}) {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  if (cachedToken) headers.Authorization = `Bearer ${cachedToken}`;

  let res;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    const err = new Error("Sunucuya ulaşılamadı. İnternet bağlantını kontrol et.");
    err.status = 0;
    throw err;
  }

  if (res.status === 401 && cachedToken) {
    await clearToken();
    onLogout && onLogout();
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail = data && data.detail;
    const err = new Error(typeof detail === "string" ? detail : "Bir sorun oluştu, tekrar dene.");
    err.status = res.status;
    throw err;
  }
  return data;
}
