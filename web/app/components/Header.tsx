"use client";

import Link from "next/link";

import { Usage, logout } from "../lib/api";

function usageText(usage: Usage) {
  if (usage.plan === "deneme") {
    const left = (usage.ideas.quota ?? 0) - usage.ideas.used;
    return `Deneme · ${Math.max(left, 0)} fikir kaldı`;
  }
  return `${usage.plan_name} · ${usage.video.quota - usage.video.used} video, ${
    usage.image.quota - usage.image.used
  } görsel kaldı`;
}

export default function Header({ usage }: { usage?: Usage | null }) {
  return (
    <header className="header">
      <Link href="/">
        <img src="/logo.png" alt="ajansAI" className="logo" />
      </Link>
      <div className="header-right">
        {usage && <span className="usage-pill">{usageText(usage)}</span>}
        <Link href="/ads" className="tag pricing-link">
          Reklamlar
        </Link>
        <Link href="/pricing" className="tag pricing-link">
          Paketler
        </Link>
        <button className="link-button" onClick={logout}>
          Çıkış
        </button>
      </div>
    </header>
  );
}
