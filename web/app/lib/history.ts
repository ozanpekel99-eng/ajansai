// Üretim geçmişi bu tarayıcıda saklanır (son 20 kayıt / araç).
// Sunucuda saklanmadığı için başka cihazda görünmez; arayüzde bu belirtilir.

export type HistoryEntry<T = any> = { id: string; title: string; at: number; data: T };

const key = (tool: string) => `ajansai_history_${tool}`;

export function readHistory<T = any>(tool: string): HistoryEntry<T>[] {
  try {
    return JSON.parse(localStorage.getItem(key(tool)) || "[]");
  } catch {
    return [];
  }
}

export function addHistory<T>(tool: string, title: string, data: T) {
  const entry: HistoryEntry<T> = { id: `${Date.now()}`, title, at: Date.now(), data };
  try {
    const list = [entry, ...readHistory<T>(tool)].slice(0, 20);
    localStorage.setItem(key(tool), JSON.stringify(list));
  } catch {
    // depolama kapalıysa geçmiş tutulmaz, üretim yine çalışır
  }
  return entry;
}

export function timeAgo(at: number) {
  const s = Math.round((Date.now() - at) / 1000);
  if (s < 60) return "az önce";
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} sa önce`;
  return new Date(at).toLocaleDateString("tr-TR");
}
