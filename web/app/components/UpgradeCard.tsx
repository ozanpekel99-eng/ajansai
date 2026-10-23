"use client";

import Link from "next/link";

import { PLAN_ORDER, money, num, usePricing } from "../lib/plans";

export type LimitReason = "chat" | "image";

const TITLE: Record<LimitReason, string> = {
  image: "Bu ayki ücretsiz görsel hakkın doldu",
  chat: "Bugünkü ücretsiz mesaj hakkın doldu",
};

/**
 * Ücretsiz hak dolunca sohbette paketleri gösterir.
 * onPick verilirse (giriş yapmış ücretsiz üye) ödeme penceresi açılır; yoksa (misafir) kayıt sayfasına gider.
 */
export default function UpgradeCard({ reason, onPick }: { reason: LimitReason; onPick?: (planId: string) => void }) {
  const pricing = usePricing();
  const plans = PLAN_ORDER.map((id) => pricing?.plans?.[id]).filter(Boolean) as NonNullable<NonNullable<typeof pricing>["plans"][string]>[];
  const free = pricing?.free;

  return (
    <section className="upgrade-card" aria-label="Paketler">
      <div className="upgrade-head">
        <strong>{TITLE[reason]}</strong>
        <span>
          Paketle kaldığın yerden devam et: aynı kalitede görsel, sınırsız sohbet, video ve Instagram reklamı.
        </span>
      </div>
      <div className="upgrade-plans">
        {plans.map((p) => {
          const featured = p.id === "pro";
          const label = `${p.name} paketini al`;
          return (
            <div key={p.id} className={`upgrade-plan ${featured ? "featured" : ""}`}>
              {featured && <span className="upgrade-tag">En çok tercih edilen</span>}
              <span className="upgrade-name">{p.name}</span>
              <span className="upgrade-price">
                {money(p.price, p.currency)} <small>/ ay + KDV</small>
              </span>
              <span className="upgrade-meta">
                {num(p.credits)} kredi · {num(p.examples.images)} görsel ya da {num(p.examples.videos["720p"])} video
              </span>
              {onPick ? (
                <button type="button" className={`btn btn-sm ${featured ? "btn-primary" : "btn-light"}`} onClick={() => onPick(p.id)}>
                  {label}
                </button>
              ) : (
                <Link className={`btn btn-sm ${featured ? "btn-primary" : "btn-light"}`} href={`/kayit?paket=${p.id}`}>
                  {label}
                </Link>
              )}
            </div>
          );
        })}
      </div>
      {!onPick && free && (
        <p className="upgrade-foot">
          Henüz hazır değil misin?{" "}
          <Link href="/kayit?paket=deneme">Ücretsiz üye ol</Link>: günde {free.chat_per_day} mesaj, ayda {free.images_per_month} görsel.
        </p>
      )}
    </section>
  );
}
