"use client";

import { PLAN_ORDER, Plan, tl, usePlans } from "../../lib/plans";
import { useSession } from "../../lib/session";
import { READY_TOOLS } from "../../lib/tools";

const PITCH: Record<string, string> = {
  baslangic: "Kendi işletmesinin hesabını yöneten esnaf için.",
  pro: "Düzenli paylaşım yapan ve reklam veren işletmeler için.",
  ajans: "Birden fazla markayı yöneten ajans ve danışmanlar için.",
};

function features(p: Plan) {
  return [
    { text: "Sınırsız içerik fikri", ok: true },
    { text: `Ayda ${p.image_quota} görsel`, ok: true },
    { text: `Ayda ${p.video_quota} dikey video`, ok: true },
    { text: "Instagram reklam taslağı (Meta)", ok: p.ads_enabled },
  ];
}

export default function Paketler() {
  const plans = usePlans();
  const { usage, openCheckout } = useSession();
  const ids = PLAN_ORDER.filter((id) => plans?.[id]);

  return (
    <div className="page">
      <section className="price-hero">
        <h1>İşine uyan paketi seç</h1>
        <p>Her paket 30 gün geçerli, otomatik yenilenmez. Ödeme iyzico güvencesiyle Türk lirası olarak alınır.</p>
      </section>

      {plans === null ? (
        <div className="plans">
          {[0, 1, 2].map((i) => (
            <div key={i} className="panel plan" style={{ minHeight: 360 }} />
          ))}
        </div>
      ) : ids.length === 0 ? (
        <div className="panel empty" style={{ marginTop: 32 }}>
          <h3>Paketler yüklenemedi</h3>
          <p>Sayfayı yenileyip tekrar dene.</p>
        </div>
      ) : (
        <div className="plans">
          {ids.map((id) => {
            const p = plans[id];
            const current = usage?.plan === id;
            return (
              <article key={id} className={`panel plan ${id === "pro" ? "featured" : ""}`}>
                {id === "pro" ? <span className="chip chip-indigo">En çok tercih edilen</span> : <span className="chip chip-muted">{p.name}</span>}
                <h2>{p.name}</h2>
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{PITCH[id]}</p>
                <div className="amount">
                  {tl(p.price_try)} <small>/ 30 gün</small>
                </div>
                <ul>
                  {features(p).map((f) => (
                    <li key={f.text} className={f.ok ? "" : "no"}>
                      {f.text}
                    </li>
                  ))}
                </ul>
                <button
                  className={`btn btn-block ${id === "pro" ? "btn-primary" : "btn-light"}`}
                  onClick={() => openCheckout(id)}
                >
                  {current ? "30 gün uzat" : `${p.name} paketini al`}
                </button>
              </article>
            );
          })}
        </div>
      )}

      {ids.length > 0 && plans && (
        <>
          <section className="section">
            <div className="section-head">
              <div>
                <h2>Paketleri karşılaştır</h2>
                <p>Deneme paketi kayıt olan herkese açıktır ve ücretsizdir.</p>
              </div>
            </div>
            <div className="panel table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th></th>
                    <th>Deneme</th>
                    {ids.map((id) => (
                      <th key={id}>{plans[id].name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Fiyat (30 gün)</td>
                    <td className="num">Ücretsiz</td>
                    {ids.map((id) => (
                      <td key={id} className="num">{tl(plans[id].price_try)}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>İçerik fikri</td>
                    <td className="num">Ayda 10</td>
                    {ids.map((id) => (
                      <td key={id}>Sınırsız</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Görsel</td>
                    <td className="num">—</td>
                    {ids.map((id) => (
                      <td key={id} className="num">{plans[id].image_quota}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Dikey video</td>
                    <td className="num">—</td>
                    {ids.map((id) => (
                      <td key={id} className="num">{plans[id].video_quota}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Meta reklam taslağı</td>
                    <td>—</td>
                    {ids.map((id) => (
                      <td key={id}>{plans[id].ads_enabled ? "Var" : "—"}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2>Hangi araç neyi kullanır?</h2>
                <p>Üretim başarısız olursa kullandığın hak otomatik iade edilir.</p>
              </div>
            </div>
            <div className="panel table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Araç</th>
                    <th>Bir kullanım</th>
                    <th>Açık olduğu paketler</th>
                  </tr>
                </thead>
                <tbody>
                  {READY_TOOLS.map((t) => (
                    <tr key={t.slug}>
                      <td>{t.name}</td>
                      <td>{t.costLabel}</td>
                      <td>{t.plan ? `${t.plan} ve üzeri` : "Tüm paketler"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
