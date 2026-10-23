"use client";

import { FormEvent, useEffect, useState } from "react";

import { api } from "../lib/api";
import { Cycle, PLAN_ORDER, cyclePrice, money, perMonth, usePlans } from "../lib/plans";
import Icon from "./Icon";

const BILLING_KEY = "ajansai_billing";

export type CreditPack = { id: string; name: string; credits: number; price: number; currency: string; vat_rate: number; per_credit: number };

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
  const canBuyCredits = !!currentPlan && currentPlan !== "deneme";
  const [kind, setKind] = useState<"plan" | "credits">(planArg?.startsWith("kredi") && canBuyCredits ? "credits" : "plan");
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [packId, setPackId] = useState(planArg?.startsWith("kredi_") ? planArg : "kredi_250");
  const [cycle, setCycle] = useState<Cycle>(cycleArg === "yearly" ? "yearly" : "monthly");
  const [planId, setPlanId] = useState(
    planArg && !planArg.startsWith("kredi") ? planArg : currentPlan && currentPlan !== "deneme" ? currentPlan : "pro",
  );
  const [billing, setBilling] = useState<Billing>({ name: "", surname: "", phone: "", city: "", address: "" });
  const [paying, setPaying] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (canBuyCredits) api<{ packs: CreditPack[] }>("/api/payments/packs").then((d) => setPacks(d.packs)).catch(() => {});
  }, [canBuyCredits]);

  useEffect(() => {
    setBilling(loadBilling());
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const update = (key: keyof Billing, value: string) => setBilling((b) => ({ ...b, [key]: value }));
  const plan = plans?.[planId];
  const pack = packs.find((p) => p.id === packId);
  const net = kind === "credits" ? pack?.price ?? 0 : plan ? cyclePrice(plan, cycle) : 0;
  const vatRate = (kind === "credits" ? pack?.vat_rate : plan?.vat_rate) ?? 20;
  const currency = (kind === "credits" ? pack?.currency : plan?.currency) || "USD";
  const ready = kind === "credits" ? !!pack : !!plan;
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
        body: JSON.stringify({ plan_id: kind === "credits" ? packId : planId, cycle, billing }),
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
          <h2 id="checkout-title">{kind === "credits" ? "Ek kredi al" : "Paket satın al"}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Kapat">
            <Icon name="close" />
          </button>
        </div>

        {canBuyCredits && (
          <div className="tabs cycle-tabs" role="tablist" aria-label="Satın alma türü">
            <button type="button" role="tab" aria-selected={kind === "plan"} className={kind === "plan" ? "active" : ""} onClick={() => setKind("plan")}>
              Paket
            </button>
            <button type="button" role="tab" aria-selected={kind === "credits"} className={kind === "credits" ? "active" : ""} onClick={() => setKind("credits")}>
              Ek kredi
            </button>
          </div>
        )}

        {kind === "credits" ? (
          <div className="plan-pick">
            {packs.map((p) => (
              <button type="button" key={p.id} className={packId === p.id ? "active" : ""} onClick={() => setPackId(p.id)} aria-pressed={packId === p.id}>
                <strong>{p.credits.toLocaleString("tr-TR")} kredi</strong>
                <span>
                  {money(p.price, p.currency)} + KDV · kredi başı {money(p.per_credit, p.currency)}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <>
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
  
          </>
        )}

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

        {kind === "credits" && pack && (
          <div className="summary">
            <div>
              <span className="muted">{pack.name}</span>
              <span>{money(net, currency)}</span>
            </div>
            <div>
              <span className="muted">KDV (%{vatRate})</span>
              <span>{money(vat, currency)}</span>
            </div>
            <div>
              <span className="muted">Nasıl kullanılır</span>
              <span>Paket kredin bitince bu krediden düşülür; ay yenilense de silinmez.</span>
            </div>
            <div className="total">
              <span>Ödenecek tutar (KDV dahil)</span>
              <span>{money(total, currency)}</span>
            </div>
          </div>
        )}

        {kind === "plan" && plan && (
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
                {cycle === "yearly"
                  ? `${(plan.credits * 12).toLocaleString("tr-TR")} kredi, tek seferde hesabına yüklenir`
                  : `${plan.credits.toLocaleString("tr-TR")} kredi (30 gün)`}
              </span>
            </div>
            <div>
              <span className="muted">Örneğin</span>
              <span>
                {plan.examples.images} görsel veya {plan.examples.videos["720p"]} video (720p, 6 sn)
              </span>
            </div>
            <div className="total">
              <span>Ödenecek tutar (KDV dahil)</span>
              <span>{money(total, plan.currency)}</span>
            </div>
          </div>
        )}

        <label className="agree">
          <input id="checkout-agree" type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />
          <span>
            <a href="/mesafeli-satis-sozlesmesi" target="_blank" rel="noreferrer">Mesafeli Satış Sözleşmesi</a>'ni ve{" "}
            <a href="/teslimat-ve-iade" target="_blank" rel="noreferrer">Teslimat ve İade Koşulları</a>'nı okudum, onaylıyorum. Kredilerin
            anında hesabıma tanımlanmasını ve kullanım başladıktan sonra cayma hakkımın olmayacağını kabul ediyorum.
          </span>
        </label>

        {error && <p className="error-text">{error}</p>}

        <button className="btn btn-primary btn-block" type="submit" disabled={paying || !ready || !agreed}>
          <Icon name="lock" size={16} />
          {paying ? "Ödeme sayfası açılıyor…" : ready ? `${money(total, currency)} öde` : "Paket seç"}
        </button>
        <p className="secure-note">Ödeme dolar (USD) olarak alınır; TL kartlarda tutar bankanın güncel kuruyla çevrilir. Kart bilgilerin iyzico'nun güvenli sayfasında alınır, ajansAI saklamaz.</p>
      </form>
    </div>
  );
}
