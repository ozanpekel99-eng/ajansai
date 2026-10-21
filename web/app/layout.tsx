import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ajansAI — KOBİ'ler için İçerik ve Reklam Asistanı",
  description: "İşletmen için sosyal medya içerik fikirleri üret, görsel/video hazırla ve reklamını ver.",
  icons: { icon: "/logo.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
