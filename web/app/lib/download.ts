/**
 * Dosyayı yeni sekme açmadan indirir. Vercel Blob dosyaları başka alan adında olduğu için
 * <a download> tek başına çalışmaz; dosya fetch ile alınıp yerel bir adresle kaydedilir.
 */
export function downloadHref(url: string): string {
  return url;
}

function nameFrom(url: string, fallback = "ajansai") {
  try {
    const last = new URL(url).pathname.split("/").pop() || "";
    return decodeURIComponent(last) || fallback;
  } catch {
    return fallback;
  }
}

export async function downloadFile(url: string, name?: string) {
  const filename = name || nameFrom(url);
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(String(res.status));
    const blob = await res.blob();
    const local = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = local;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(local), 10_000);
  } catch {
    window.open(url, "_blank", "noopener");
  }
}

/** <a> için tıklama: sayfayı değiştirmeden indirir. */
export function onDownload(url: string, name?: string) {
  return (e: { preventDefault: () => void }) => {
    e.preventDefault();
    void downloadFile(url, name);
  };
}
