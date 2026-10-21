"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { api } from "../../lib/api";
import { tl } from "../../lib/plans";
import { useSession } from "../../lib/session";

type Payment = {
  payment_id: string;
  plan_name: string;
  amount_try: number;
  status: "success" | "failure" | "pending";
  created_at: string;
};

const STATUS_LABEL = { success: "Ödendi", failure: "Başarısız", pending: "Bekliyor" };

const fmtDate = (iso: string) =>
  new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

export default function Faturalandirma() {
  const { usage, openCheckout } = useSession();
  const [payments, setPayments] = useState<Payment[] | null>(null);

  useEffect(() => {
    api<{ payments: Payment[] }>("/api/payments/")
      .then((d) => setPayments(d.payments))
      .catch(() => setPayments([]));
  }, []);

  const trial = usage?.plan === "deneme";
  const daysLeft = usage?.plan_expires_at
    ? Math.max(0, Math.ceil((new Date(usage.plan_expires_at).getTime() - Date.now()) / 86400000))
    : null;

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Konum">
        <strong>Faturalandırma</strong>
      </nav>

      <section className="panel balance">
        <div className="label">Mevcut paketin</div>
        <div className="big">{usage?.plan_name ?? "…"}</div>
        <div className="muted" style={{ fontSize: 14 }}>
          {trial
            ? "Ücretsiz deneme: ayda 10 içerik fikri"
            : usage?.plan_expires_at
              ? `${fmtDate(usage.plan_expires_at)} tarihine kadar geçerli · ${daysLeft} gün kaldı`
              : ""}
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => openCheckout(trial ? "pro" : usage?.plan)}>
            {trial ? "Paket satın al" : "Paketi uzat veya yükselt"}
          </button>
          <Link className="btn btn-ghost" href="/paketler">
            Paketleri karşılaştır
          </Link>
        </div>
      </section>

      {usage && (
        <div className="stats" style={{ marginTop: 16 }}>
          <div className="panel stat">
            <div className="name">İçerik fikri</div>
            <div className="value">
              {usage.ideas.used} <small>/ {usage.ideas.quota ?? "sınırsız"}</small>
            </div>
            <div className="foot">Bu dönem kullanılan</div>
          </div>
          <div className="panel stat">
            <div className="name">Görsel</div>
            <div className="value">
              {usage.image.used} <small>/ {usage.image.quota}</small>
            </div>
            <div className="foot">Bu dönem kullanılan</div>
          </div>
          <div className="panel stat">
            <div className="name">Video</div>
            <div className="value">
              {usage.video.used} <small>/ {usage.video.quota}</small>
            </div>
            <div className="foot">Bu dönem kullanılan</div>
          </div>
        </div>
      )}

      <section className="section">
        <div className="section-head">
          <div>
            <h2>Ödeme geçmişi</h2>
            <p>Kart bilgilerin ajansAI'da saklanmaz; ödemeler iyzico üzerinden alınır.</p>
          </div>
        </div>
        {payments === null ? null : payments.length === 0 ? (
          <div className="panel empty">
            <h3>Henüz ödeme yok</h3>
            <p>Bir paket aldığında faturaların burada listelenir.</p>
          </div>
        ) : (
          <div className="panel table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Tarih</th>
                  <th>Paket</th>
                  <th>Tutar</th>
                  <th>Durum</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.payment_id}>
                    <td>{fmtDate(p.created_at)}</td>
                    <td>{p.plan_name}</td>
                    <td className="num">{tl(p.amount_try)}</td>
                    <td>
                      <span className={`status-pill ${p.status}`}>{STATUS_LABEL[p.status] ?? p.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
