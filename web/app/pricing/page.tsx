"use client";

import { FormEvent, useEffect, useState } from "react";

import Header from "../components/Header";
import { api } from "../lib/api";
import { useAuth } from "../lib/useAuth";

type Plan = {
  name: string;
  price_try: number;
  price_usd: number;
  video_quota: number;
  image_quota: number;
  ads_enabled: boolean;
};

export default function Pricing() {
  const { ready, usage } = useAuth();
  const [plans, setPlans] = useState<Record<string, Plan>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [billing, setBilling] = useState({ name: "", surname: "", phone: "", city: "", address: "" });
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ plans: Record<string, Plan> }>("/api/plans/")
      .then((data) => setPlans(data.plans))
      .catch((err) => setError(err.message));
  }, []);

  const update = (key: string, value: string) => setBilling((prev) => ({ ...prev, [key]: value }));

  const pay = async (e: FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    setPaying(true);
    setError("");
    try {
      const data = await api<{ payment_page_url: string }>("/api/payments/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_id: selected, billing }),
      });
      // iyzico'nun güvenli ödeme sayfasına geçiş; kart bilgisi bizim sunucumuza hiç gelmez.
      window.location.href = data.payment_page_url;
    } catch (err: any) {
      setError(err.message);
      setPaying(false);
    }
  };

  if (!ready) return null;

  const currentPlan = usage?.plan;
  const expires = usage?.plan_expires_at ? new Date(usage.plan_expires_at).toLocaleDateString("tr-TR") : null;

  return (
    <div className="page">
      <Header usage={usage} />

      <section className="hero">
        <h1>İşine uygun paketi seç.</h1>
        <p>
          Paketler 30 gün geçerlidir; ödeme iyzico güvencesiyle alınır. Reklam
          entegrasyonu Pro ile birlikte açılıyor.
        </p>
      </section>

      {expires && currentPlan !== "deneme" && (
        <div className="notice">
          {usage?.plan_name} paketin {expires} tarihine kadar geçerli. Aynı paketi şimdi yenilersen kalan günlerin korunur.
        </div>
      )}

      <div className="pricing-grid">
        {Object.entries(plans).map(([id, plan]) => (
          <div className={`pricing-card ${currentPlan === id ? "active" : ""}`} key={id}>
            {currentPlan === id && <span className="current-tag">Mevcut paketin</span>}
            <h3>{plan.name}</h3>
            <div className="price">
              ₺{plan.price_try.toLocaleString("tr-TR")}
              <span>/30 gün</span>
            </div>
            <div className="price-usd">${plan.price_usd}</div>

            <ul>
              <li>{plan.video_quota} video</li>
              <li>{plan.image_quota} görsel</li>
              <li>Sınırsız içerik fikri</li>
              <li>{plan.ads_enabled ? "Reklam entegrasyonu dahil" : "Reklam entegrasyonu yok"}</li>
            </ul>

            <button className="primary" onClick={() => setSelected(id)} disabled={paying}>
              {currentPlan === id ? "Yenile" : "Bu paketi seç"}
            </button>
          </div>
        ))}
      </div>

      {selected && plans[selected] && (
        <section className="checkout">
          <h2>
            {plans[selected].name} paketi · ₺{plans[selected].price_try.toLocaleString("tr-TR")}
          </h2>
          <form className="form-card" onSubmit={pay}>
            <div className="field">
              <label>Ad</label>
              <input required value={billing.name} onChange={(e) => update("name", e.target.value)} autoComplete="given-name" />
            </div>
            <div className="field">
              <label>Soyad</label>
              <input required value={billing.surname} onChange={(e) => update("surname", e.target.value)} autoComplete="family-name" />
            </div>
            <div className="field">
              <label>Cep telefonu</label>
              <input
                required
                type="tel"
                value={billing.phone}
                onChange={(e) => update("phone", e.target.value)}
                placeholder="05xx xxx xx xx"
                autoComplete="tel"
              />
            </div>
            <div className="field">
              <label>Şehir</label>
              <input required value={billing.city} onChange={(e) => update("city", e.target.value)} autoComplete="address-level1" />
            </div>
            <div className="field full">
              <label>Fatura adresi</label>
              <textarea
                required
                rows={2}
                value={billing.address}
                onChange={(e) => update("address", e.target.value)}
                autoComplete="street-address"
              />
            </div>
            <div className="submit-row">
              <button className="primary" type="submit" disabled={paying}>
                {paying ? "Ödeme sayfası açılıyor…" : "iyzico ile öde"}
              </button>
              <button type="button" className="link-button" style={{ color: "rgba(255,255,255,0.6)" }} onClick={() => setSelected(null)}>
                Vazgeç
              </button>
              {error && <span className="error-text">{error}</span>}
            </div>
          </form>
        </section>
      )}

      {!selected && error && <div className="notice error">{error}</div>}
    </div>
  );
}
