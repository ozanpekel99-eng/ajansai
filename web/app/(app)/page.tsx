"use client";

import Link from "next/link";

import Icon from "../components/Icon";
import ToolCard from "../components/ToolCard";
import { firstName, onboardingSteps, useSession } from "../lib/session";
import { TOOLS } from "../lib/tools";

function greeting() {
  const h = new Date().getHours();
  if (h < 6) return "İyi geceler";
  if (h < 12) return "Günaydın";
  if (h < 18) return "İyi günler";
  return "İyi akşamlar";
}

export default function Dashboard() {
  const { user, usage, metaConnected, openCheckout } = useSession();
  const steps = onboardingSteps(usage, metaConnected);
  const done = steps.filter((s) => s.done).length;

  const stepCopy: Record<string, { text: string; action: React.ReactNode }> = {
    account: { text: "Kayıt oldun, deneme paketin açıldı.", action: <span className="chip">Tamamlandı</span> },
    idea: {
      text: "İşletmeni anlat, dört platforma özel fikir al.",
      action: (
        <Link href="/araclar/fikir" className="btn btn-light btn-sm">
          Fikir üret
        </Link>
      ),
    },
    plan: {
      text: "Görsel ve video üretimi paketle açılır.",
      action: (
        <button className="btn btn-light btn-sm" onClick={() => openCheckout()}>
          Paketleri gör
        </button>
      ),
    },
    meta: {
      text: "Kampanya taslaklarını buradan oluştur. Pro ve Ajans paketlerinde.",
      action: (
        <Link href="/araclar/reklam" className="btn btn-ghost btn-sm">
          Bağla
        </Link>
      ),
    },
  };

  return (
    <div className="page">
      <div className="greet">
        <h1>
          {greeting()}
          {user ? `, ${firstName(user)}` : ""}
        </h1>
        <Link href="/araclar/fikir" className="btn btn-primary">
          <Icon name="sparkle" size={16} />
          Yeni içerik üret
        </Link>
      </div>

      {done < steps.length && (
        <section className="panel steps" aria-labelledby="steps-title">
          <div className="steps-head">
            <h2 id="steps-title">ajansAI'ı kurmaya başla</h2>
            <span className="faint">
              {done} / {steps.length} tamamlandı
            </span>
          </div>
          <div className="steps-grid">
            {steps.map((s) => (
              <div className="step" key={s.key}>
                <div className={`check-item ${s.done ? "done" : ""}`}>
                  <span className="dot" />
                </div>
                <h3>{s.title}</h3>
                <p>{stepCopy[s.key].text}</p>
                {!s.done && stepCopy[s.key].action}
                {s.done && s.key === "account" && stepCopy.account.action}
              </div>
            ))}
          </div>
        </section>
      )}

      {usage?.plan === "deneme" && (
        <div className="section promo">
          <span className="promo-icon">
            <Icon name="gift" size={20} />
          </span>
          <div>
            <h3>Görsel ve video üretimini aç</h3>
            <p>Başlangıç paketi 200 kredi: örneğin 50 görsel ya da 16 kısa video.</p>
          </div>
          <button className="btn btn-light" onClick={() => openCheckout("baslangic")}>
            Paketi seç
          </button>
        </div>
      )}

      <section className="section">
        <div className="section-head">
          <div>
            <h2>Araçlar</h2>
            <p>İçerik fikrinden reklam kampanyasına kadar her şey tek yerde.</p>
          </div>
          <Link href="/araclar" className="btn btn-ghost btn-sm">
            Tümünü gör
          </Link>
        </div>
        <div className="tool-grid">
          {TOOLS.slice(0, 4).map((t) => (
            <ToolCard key={t.slug} tool={t} />
          ))}
        </div>
      </section>
    </div>
  );
}
