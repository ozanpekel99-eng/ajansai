"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";

import SiteFooter from "../components/SiteFooter";
import { useSearchParams } from "next/navigation";

import SocialLogin from "../components/SocialLogin";
import { api, setToken } from "../lib/api";
import { Cycle, PENDING_PLAN_KEY, PLAN_ORDER, money, num, perMonth, usePricing } from "../lib/plans";

const PITCH: Record<string, string> = {
  deneme: "Denemek için: sohbet ve görsel üretimi, kart gerekmez.",
  baslangic: "Kendi işletmesinin hesabını yöneten esnaf için.",
  pro: "Düzenli paylaşım yapan ve reklam veren işletmeler için.",
  ajans: "Birden fazla markayı yöneten ajans ve danışmanlar için.",
};

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <Signup />
    </Suspense>
  );
}

function Signup() {
  const params = useSearchParams();
  const pricing = usePricing();
  const [plan, setPlan] = useState<string | null>(params.get("paket"));
  const [cycle, setCycle] = useState<Cycle>("monthly");

  const choose = (id: string) => {
    try {
      if (id === "deneme") localStorage.removeItem(PENDING_PLAN_KEY);
      else localStorage.setItem(PENDING_PLAN_KEY, `${id}:${cycle}`);
    } catch {
      // depolama kapalıysa paket seçimi kayıttan sonra panelden yapılır
    }
    setPlan(id);
  };

  // Kayıt/giriş sonrası panel açılır; ücretli paket seçildiyse ödeme penceresi orada açılır.
  const done = () => {
    window.location.href = "/";
  };

  if (!plan) {
    const ids = ["deneme", ...PLAN_ORDER.filter((id) => pricing?.plans?.[id])];
    return (
      <div className="signup">
        <header className="guest-top">
          <Link href="/ucretsiz">
            <img src="/logo-on-dark.png" alt="ajansAI" />
          </Link>
          <div className="actions">
            <Link href="/login" className="btn btn-ghost btn-sm">
              Giriş yap
            </Link>
          </div>
        </header>
        <main className="page">
          <section className="price-hero">
            <h1>Hangi paketle başlamak istersin?</h1>
            <p>Ücretsiz paketle hemen başlayabilir, istediğin zaman yükseltebilirsin. Fiyatlara KDV eklenir; otomatik yenilenmez.</p>
          </section>
          <div className="cycle-switch">
            <div className="tabs" role="tablist" aria-label="Ödeme dönemi">
              <button type="button" role="tab" aria-selected={cycle === "monthly"} className={cycle === "monthly" ? "active" : ""} onClick={() => setCycle("monthly")}>
                Aylık
              </button>
              <button type="button" role="tab" aria-selected={cycle === "yearly"} className={cycle === "yearly" ? "active" : ""} onClick={() => setCycle("yearly")}>
                Yıllık · %20 indirim
              </button>
            </div>
          </div>
          <div className="plans plans-4">
            {ids.map((id) => {
              const p = id === "deneme" ? pricing?.trial : pricing?.plans?.[id];
              return (
                <article key={id} className={`panel plan ${id === "pro" ? "featured" : ""}`}>
                  {id === "pro" ? <span className="chip chip-indigo">En çok tercih edilen</span> : <span className="chip chip-muted">{p?.name ?? ""}</span>}
                  <h2>{id === "deneme" ? "Ücretsiz" : p?.name}</h2>
                  <p className="muted" style={{ margin: 0, fontSize: 14 }}>{PITCH[id]}</p>
                  <div className="amount">
                    {id === "deneme" ? "$0" : p ? money(perMonth(p, cycle), p.currency) : "…"}{" "}
                    <small>{id === "deneme" ? "süresiz" : "/ ay + KDV"}</small>
                  </div>
                  {id !== "deneme" && p && (
                    <p className="plan-sub" style={{ marginTop: -6 }}>
                      {cycle === "yearly" ? `Yıllık ${money(p.price_yearly, p.currency)} + KDV tek ödeme` : "30 gün geçerli"}
                    </p>
                  )}
                  <ul>
                    {id === "deneme" ? (
                      <>
                        <li>Günde {pricing?.free?.chat_per_day ?? 20} sohbet mesajı</li>
                        <li>30 günde {pricing?.free?.images_per_month ?? 6} görsel</li>
                        <li>Görselden görsel üretimi</li>
                        <li className="no">Video ve Meta reklamları</li>
                      </>
                    ) : p ? (
                      <>
                        <li>Her ay {num(p.credits)} kredi</li>
                        <li>Sınırsız sohbet (mesaj başı 1 kredi), dosya ekleme</li>
                        <li>{num(p.examples.images)} yüksek kaliteli görsel ya da {num(p.examples.videos["720p"])} kısa video</li>
                        <li className={p.ads_enabled ? "" : "no"}>Instagram reklamları (Meta)</li>
                      </>
                    ) : null}
                  </ul>
                  <button className={`btn btn-block ${id === "pro" ? "btn-primary" : "btn-light"}`} onClick={() => choose(id)}>
                    {id === "deneme" ? "Ücretsiz başla" : `${p?.name ?? ""} ile kaydol`}
                  </button>
                </article>
              );
            })}
          </div>
        </main>
        <SiteFooter />
      </div>
    );
  }

  return <AccountStep plan={plan} planName={plan === "deneme" ? "Ücretsiz" : pricing?.plans?.[plan]?.name || plan} onBack={() => setPlan(null)} onDone={done} />;
}

function AccountStep({ plan, planName, onBack, onDone }: { plan: string; planName: string; onBack: () => void; onDone: () => void }) {
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ token: string }>("/api/auth/register", { method: "POST", body: JSON.stringify(form) });
      setToken(data.token);
      onDone();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth">
      <div className="auth-form">
        <img src="/logo-on-dark.png" alt="ajansAI" className="logo" />
        <h1>Hesabını oluştur</h1>
        <p>
          Seçtiğin paket: <strong>{planName}</strong>{" "}
          <button type="button" className="link-btn" onClick={onBack}>
            Değiştir
          </button>
          {plan !== "deneme" && <><br />Hesabını oluşturunca ödeme ekranı açılır.</>}
        </p>

        <SocialLogin onDone={onDone} />

        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="k-name">Ad soyad</label>
            <input id="k-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoComplete="name" />
          </div>
          <div className="field">
            <label htmlFor="k-email">E-posta</label>
            <input id="k-email" required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="email" />
          </div>
          <div className="field">
            <label htmlFor="k-pass">Şifre</label>
            <input
              id="k-pass"
              required
              type="password"
              minLength={8}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              autoComplete="new-password"
              placeholder="En az 8 karakter"
            />
          </div>
          {error && <div className="notice error">{error}</div>}
          <button className="btn btn-primary btn-block" type="submit" disabled={loading} style={{ marginTop: 8 }}>
            {loading ? "Bekle…" : "Hesap oluştur"}
          </button>
        </form>

        <p className="faint" style={{ fontSize: 12.5, marginTop: 12 }}>
          Hesap oluşturarak <Link href="/kosullar">Kullanım Koşulları</Link>'nı ve <Link href="/gizlilik">Gizlilik Politikası</Link>'nı kabul
          etmiş olursun.
        </p>
        <div className="switch-link">
          Zaten hesabın var mı? <Link href="/login">Giriş yap</Link>
        </div>
      </div>
      <div className="auth-art" aria-hidden="true">
        <div className="tile" style={{ top: "12%", left: "14%", width: 120, height: 120 }} />
        <div className="tile w" style={{ top: "20%", left: "52%", width: 64, height: 64 }} />
        <div className="tile" style={{ top: "38%", left: "34%", width: 180, height: 90 }} />
        <div className="tile w" style={{ top: "8%", right: "10%", width: 28, height: 28 }} />
        <div className="tile" style={{ top: "48%", right: "12%", width: 72, height: 160 }} />
        <p className="quote">Sohbet et, görselini üret, reklamını yayınla. Hepsi tek yerde.</p>
      </div>
    </div>
  );
}
