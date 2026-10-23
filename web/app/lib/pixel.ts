// Meta Pikseli (ajansAI Web veri seti). Reklamların satışa göre optimize edilmesi için
// kayıt, ödeme başlatma ve satın alma olaylarını Meta'ya bildirir.
export const META_PIXEL_ID = "1084755444379431";

type Fbq = (...args: unknown[]) => void;

export function track(event: string, params?: Record<string, unknown>, eventId?: string) {
  if (typeof window === "undefined") return;
  const fbq = (window as unknown as { fbq?: Fbq }).fbq;
  if (!fbq) return;
  try {
    if (eventId) fbq("track", event, params ?? {}, { eventID: eventId });
    else fbq("track", event, params ?? {});
  } catch {
    // piksel engellendiyse (reklam engelleyici) sessizce geç
  }
}
