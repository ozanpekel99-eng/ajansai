import "./globals.css";
import { Analytics } from "@vercel/analytics/next";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "ajansAI",
  description: "Her şeyi sorabileceğin yapay zeka asistanı: sohbet et, görsel ve video üret, Instagram reklamını yayınla.",
  icons: { icon: "/icon.png", apple: "/icon.png" },
};

export const viewport: Viewport = {
  themeColor: "#000000",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
