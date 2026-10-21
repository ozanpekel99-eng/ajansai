"use client";

import Link from "next/link";

import { useSession } from "../../lib/session";

function Row({ name, used, quota, href }: { name: string; used: number; quota: number | null; href: string }) {
  const pct = quota ? Math.min(100, Math.round((used / quota) * 100)) : 0;
  return (
    <div className="panel stat">
      <div className="name">{name}</div>
      <div className="value">
        {quota === null ? used : Math.max(quota - used, 0)}{" "}
        <small>{quota === null ? "kullanıldı · sınırsız" : quota === 0 ? "paketinde yok" : `/ ${quota} kaldı`}</small>
      </div>
      {quota !== null && quota > 0 && (
        <div className="meter dark" role="progressbar" aria-valuenow={used} aria-valuemin={0} aria-valuemax={quota}>
          <span style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="foot">
        <Link href={href} style={{ color: "inherit" }}>
          Araca git
        </Link>
      </div>
    </div>
  );
}

export default function Kullanim() {
  const { usage, openCheckout } = useSession();

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Konum">
        <strong>Kullanım</strong>
      </nav>

      <div className="section-head" style={{ marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 28 }}>Bu dönemki kullanımın</h2>
          <p>
            {usage?.plan === "deneme"
              ? "Deneme paketinde haklar her ay yenilenir."
              : "Haklar paketini aldığın gün başlar ve 30 gün geçerlidir."}
          </p>
        </div>
        <button className="btn btn-light btn-sm" onClick={() => openCheckout()}>
          Daha fazla hak al
        </button>
      </div>

      {usage && (
        <div className="stats">
          <Row name="İçerik fikri" used={usage.ideas.used} quota={usage.ideas.quota} href="/araclar/fikir" />
          <Row name="Görsel" used={usage.image.used} quota={usage.image.quota} href="/araclar/gorsel" />
          <Row name="Video" used={usage.video.used} quota={usage.video.quota} href="/araclar/video" />
        </div>
      )}

      <div className="panel" style={{ marginTop: 16, padding: 18 }}>
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>
          Başarısız olan üretimlerin hakkı otomatik iade edilir. Meta reklam taslakları hak düşürmez; reklam bütçesi kendi Meta
          hesabından harcanır.
        </p>
      </div>
    </div>
  );
}
