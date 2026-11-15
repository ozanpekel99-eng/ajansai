// KVKK çerez onayı: Meta Pikseli yalnızca kullanıcı "Kabul et" derse yüklenir.
// Seçim tarayıcıda (localStorage) saklanır; gizli pencerede veya engellenmiş depolamada
// seçim hatırlanamaz ve bant yeniden gösterilir (varsayılan: onay yok).

export type Consent = "granted" | "denied";

export const CONSENT_KEY = "ajansai_cerez_onayi";
/** Seçim değiştiğinde (bant veya "Çerez tercihleri" bağlantısı) yayınlanan olay. */
export const CONSENT_EVENT = "ajansai:cerez-onayi";
/** Bandı yeniden açmak için yayınlanan olay (alt bilgideki "Çerez tercihleri"). */
export const CONSENT_OPEN_EVENT = "ajansai:cerez-tercihleri";

export function parseConsent(raw: string | null | undefined): Consent | null {
  return raw === "granted" || raw === "denied" ? raw : null;
}

// Depolama engelliyse seçim bu sekme açık kaldığı sürece bellekte tutulur.
let sessionConsent: Consent | null = null;

export function readConsent(): Consent | null {
  if (typeof window === "undefined") return null;
  try {
    return parseConsent(window.localStorage.getItem(CONSENT_KEY)) ?? sessionConsent;
  } catch {
    return sessionConsent;
  }
}

export function saveConsent(value: Consent) {
  if (typeof window === "undefined") return;
  sessionConsent = value;
  try {
    window.localStorage.setItem(CONSENT_KEY, value);
  } catch {
    // depolama engelli: seçim yalnızca bu sayfa açıkken geçerli olur
  }
  window.dispatchEvent(new CustomEvent<Consent>(CONSENT_EVENT, { detail: value }));
}

export function openConsentSettings() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(CONSENT_OPEN_EVENT));
}
