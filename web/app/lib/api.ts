// Backend ile konuşan tek yardımcı. Giriş token'ı tarayıcıda saklanır ve her
// isteğe Authorization başlığı olarak eklenir. Token geçersizse kullanıcı
// giriş sayfasına yönlendirilir.

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "ajansai_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Gizli sekme vb. durumlarda saklanamazsa oturum sayfa yenilenene kadar sürmez
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // yok say
  }
}

export function logout() {
  clearToken();
  window.location.href = "/login";
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** JSON döndüren API çağrısı. Hata durumunda backend'in Türkçe mesajıyla ApiError fırlatır. */
export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, "Sunucuya ulaşılamadı. İnternet bağlantını kontrol edip tekrar dene.");
  }

  if (res.status === 401 && token) {
    // Oturum düşmüş: giriş sayfasına gönder
    logout();
    throw new ApiError(401, "Oturumun sona erdi, tekrar giriş yap.");
  }

  let data: any = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? "Lütfen alanları kontrol et."
          : "Bir sorun oluştu, lütfen tekrar dene.";
    throw new ApiError(res.status, message);
  }
  return data as T;
}

export type VideoResolution = "720p" | "1080p" | "4k";
export type VideoDuration = 5 | 7 | 10;

export type CreditCosts = {
  idea_per_2: number;
  chat_message: number;
  chat_attachment: number;
  describe: number;
  image: number;
  ads_draft: number;
  /** çözünürlük → süre ("5" | "7" | "10") → kredi */
  video: Record<VideoResolution, Record<string, number>>;
  video_audio: Record<VideoResolution, Record<string, number>>;
};

export type Usage = {
  plan: string;
  plan_name: string;
  plan_expires_at: string | null;
  period_start: string;
  period_end: string;
  credits: { total: number; used: number; remaining: number };
  video_enabled: boolean;
  ads_enabled: boolean;
  costs: CreditCosts;
  counts: { idea: number; image: number; video: number; ads_draft: number };
};
