import "./globals.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "ajansAI — KOBİ'ler için içerik ve reklam asistanı",
  description: "İşletmen için sosyal medya içerik fikirleri üret, görsel ve video hazırla, Meta reklamlarını yönet.",
  icons: { icon: "/icon.png", apple: "/icon.png" },
};

export const viewport: Viewport = {
  themeColor: "#000000",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
