"use client";

import { FormEvent, useEffect, useState } from "react";

import { api } from "../lib/api";
import { Cycle, PLAN_ORDER, cyclePrice, money, perMonth, usePlans } from "../lib/plans";
import Icon from "./Icon";

const BILLING_KEY = "ajansai_billing";

type Billing = { name: string; surname: string; phone: string; city: string; address: string };

function loadBilling(): Billing {
  const empty = { name: "", surname: "", phone: "", city: "", address: "" };
  try {
    return { ...empty, ...JSON.parse(localStorage.getItem(BILLING_KEY) || "{}") };
  } catch {
    return empty;
  }
}

export default function CheckoutModal({
  initialPlan,
  currentPlan,
  onClose,
}: {
  initialPlan?: string;
  currentPlan?: string;
  onClose: () => void;
}) {
  const plans = usePlans();
  const [planArg, cycleArg] = (initialPlan || "").split(":");
  const [cycle, setCycle] = useState<Cycle>(cycleArg === "yearly" ? "yearly" : "monthly");
  const [planId, setPlanId] = useState(planArg || (currentPlan && currentPlan !== "deneme" ? currentPlan : "pro"));
  const [billing, setBilling] = useState<Billing>({ name: "", surname: "", phone: "", city: "", address: "" });
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setBilling(loadBilling());
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const update = (key: keyof Billing, value: string) => setBilling((b) => ({ ...b, [key]: value }));
  const plan = plans?.[planId];
  const net = plan ? cyclePrice(plan, cycle) : 0;
  const vatRate = plan?.vat_rate ?? 20;
  const vat = Math.round(net * vatRate) / 100;
  const total = Math.round((net + vat) * 100) / 100;

  const pay = async (e: FormEvent) => {
    e.preventDefault();
    setPaying(true);
    setError("");
    try {
      try {
        localStorage.setItem(BILLING_KEY, JSON.stringify(billing));
      } catch {
        // saklanamazsa bir dahaki sefere tekrar sorulur
      }
      const data = await api<{ payment_page_url: string }>("/api/payments/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_id: planId, cycle, billing }),
      });
      window.location.href = data.payment_page_url;
    } catch (err: any) {
      setError(err.message);
      setPaying(false);
    }
  };

  return (
    <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" onSubmit={pay} role="dialog" aria-modal="true" aria-labelledby="checkout-title">
        <div className="modal-head">
          <h2 id="checkout-title">Paket satın al</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Kapat">
            <Icon name="close" />
          </button>
        </div>

        <div className="tabs cycle-tabs" role="tablist" aria-label="Ödeme dönemi">
          <button type="button" role="tab" aria-selected={cycle === "monthly"} className={cycle === "monthly" ? "active" : ""} onClick={() => setCycle("monthly")}>
            Aylık
          </button>
          <button type="button" role="tab" aria-selected={cycle === "yearly"} className={cycle === "yearly" ? "active" : ""} onClick={() => setCycle("yearly")}>
            Yıllık · %{plan?.yearly_discount ?? 20} indirim
          </button>
        </div>

        <div className="plan-pick">
          {PLAN_ORDER.filter((id) => plans?.[id]).map((id) => (
            <button
              type="button"
              key={id}
              className={planId === id ? "active" : ""}
              onClick={() => setPlanId(id)}
              aria-pressed={planId === id}
            >
              <strong>{plans![id].name}</strong>
              <span>
                {money(perMonth(plans![id], cycle), plans![id].currency)}/ay + KDV · {plans![id].credits} kredi/ay
              </span>
            </button>
          ))}
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="b-name">Ad</label>
            <input id="b-name" required value={billing.name} onChange={(e) => update("name", e.target.value)} autoComplete="given-name" />
          </div>
          <div className="field">
            <label htmlFor="b-surname">Soyad</label>
            <input id="b-surname" required value={billing.surname} onChange={(e) => update("surname", e.target.value)} autoComplete="family-name" />
          </div>
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="b-phone">Cep telefonu</label>
            <input id="b-phone" required type="tel" placeholder="05xx xxx xx xx" value={billing.phone} onChange={(e) => update("phone", e.target.value)} autoComplete="tel" />
          </div>
          <div className="field">
            <label htmlFor="b-city">Şehir</label>
            <input id="b-city" required value={billing.city} onChange={(e) => update("city", e.target.value)} autoComplete="address-level1" />
          </div>
        </div>
        <div className="field">
          <label htmlFor="b-address">Fatura adresi</label>
          <textarea id="b-address" required rows={2} value={billing.address} onChange={(e) => update("address", e.target.value)} autoComplete="street-address" />
        </div>

        {plan && (
          <div className="summary">
            <div>
              <span className="muted">
                {plan.name} paketi, {cycle === "yearly" ? "12 ay" : "30 gün"}
              </span>
              <span>{money(net, plan.currency)}</span>
            </div>
            <div>
              <span className="muted">KDV (%{vatRate})</span>
              <span>{money(vat, plan.currency)}</span>
            </div>
            <div>
              <span className="muted">Dahil</span>
              <span>
                Her 30 günde {plan.credits.toLocaleString("tr-TR")} kredi{cycle === "yearly" ? " (12 kez yenilenir)" : ""}
              </span>
            </div>
            <div>
              <span className="muted">Örneğin</span>
              <span>
                {plan.examples.images} görsel veya {plan.examples.videos["720p"]} video (720p, 5 sn)
              </span>
            </div>
            <div className="total">
              <span>Ödenecek tutar (KDV dahil)</span>
              <span>{money(total, plan.currency)}</span>
            </div>
          </div>
        )}

        {error && <p className="error-text">{error}</p>}

        <button className="btn btn-primary btn-block" type="submit" disabled={paying || !plan}>
          <Icon name="lock" size={16} />
          {paying ? "Ödeme sayfası açılıyor…" : plan ? `${money(total, plan.currency)} öde` : "Paket seç"}
        </button>
        <p className="secure-note">Ödeme dolar (USD) olarak alınır; TL kartlarda tutar bankanın güncel kuruyla çevrilir. Kart bilgilerin iyzico'nun güvenli sayfasında alınır, ajansAI saklamaz.</p>
      </form>
    </div>
  );
}
