/**
 * İndirme bağlantısı: Vercel Blob dosyalarına ?download=1 eklenir; sunucu dosyayı
 * "attachment" olarak gönderir ve tarayıcı yeni sekme açmadan indirir.
 * (Farklı alan adındaki dosyalarda <a download> tek başına çalışmaz.)
 */
export function downloadHref(url: string): string {
  if (!url || url.startsWith("data:") || url.startsWith("blob:")) return url;
  try {
    const u = new URL(url);
    if (u.hostname.endsWith(".blob.vercel-storage.com")) {
      u.searchParams.set("download", "1");
      return u.toString();
    }
  } catch {
    // geçersiz adres: olduğu gibi
  }
  return url;
}
