"use client";

import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import { num } from "../../lib/plans";
import { useSession } from "../../lib/session";

type CreditEvent = {
  id: string;
  action: string;
  label: string;
  credits: number;
  detail: string;
  refunded: boolean;
  created_at: string;
};

const fmtDate = (iso: string, withTime = false) =>
  new Date(iso).toLocaleString("tr-TR", {
    day: "numeric",
    month: "long",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : { year: "numeric" }),
  });

export default function Kullanim() {
  const { usage, openCheckout } = useSession();
  const [events, setEvents] = useState<CreditEvent[] | null>(null);

  useEffect(() => {
    api<{ events: CreditEvent[] }>("/api/plans/history")
      .then((d) => setEvents(d.events))
      .catch(() => setEvents([]));
  }, [usage?.credits.used]);

  const c = usage?.credits;
  const pct = c && c.total ? Math.round((c.remaining / c.total) * 100) : 0;

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Konum">
        <strong>Kullanım</strong>
      </nav>

      <section className="panel balance">
        <div className="label">Kalan kredin</div>
        <div className="big">{c ? num(c.remaining) : "…"}</div>
        {c && usage && (
          <>
            <div className="meter dark" style={{ maxWidth: 360, margin: "10px auto" }} role="progressbar" aria-valuenow={c.remaining} aria-valuemin={0} aria-valuemax={c.total}>
              <span style={{ width: `${pct}%` }} />
            </div>
            <div className="muted" style={{ fontSize: 14 }}>
              {usage.plan_name} paketi · {num(c.total)} krediden {num(c.used)} kredi harcandı · {fmtDate(usage.period_end)} tarihinde yenilenir
            </div>
          </>
        )}
        <div className="actions">
          <button className="btn btn-primary" onClick={() => openCheckout(usage?.plan === "deneme" ? "baslangic" : usage?.plan)}>
            Kredi al
          </button>
        </div>
      </section>

      {usage && (
        <div className="stats" style={{ marginTop: 16, gridTemplateColumns: "repeat(4, 1fr)" }}>
          {[
            ["İçerik fikri üretimi", usage.counts.idea],
            ["Görsel", usage.counts.image],
            ["Video", usage.counts.video],
            ["Reklam taslağı", usage.counts.ads_draft],
          ].map(([name, count]) => (
            <div key={name as string} className="panel stat">
              <div className="name">{name}</div>
              <div className="value">{count}</div>
              <div className="foot">Bu dönem</div>
            </div>
          ))}
        </div>
      )}

      <section className="section">
        <div className="section-head">
          <div>
            <h2>Kredi hareketleri</h2>
            <p>Her üretimde kaç kredi harcandığı. Başarısız üretimlerin kredisi iade edilir.</p>
          </div>
        </div>
        {events === null ? null : events.length === 0 ? (
          <div className="panel empty">
            <h3>Henüz kredi harcamadın</h3>
            <p>İlk üretimini yaptığında burada görünecek.</p>
          </div>
        ) : (
          <div className="panel table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Tarih</th>
                  <th>İşlem</th>
                  <th>Ayrıntı</th>
                  <th>Kredi</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td>{fmtDate(e.created_at, true)}</td>
                    <td>{e.label}</td>
                    <td className="muted" style={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {e.detail}
                    </td>
                    <td className="num">
                      {e.refunded ? (
                        <span className="status-pill success">İade edildi</span>
                      ) : e.credits === 0 ? (
                        "Ücretsiz"
                      ) : (
                        `−${e.credits}`
                      )}
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
