"use client";

import { CreditCosts } from "../../lib/api";
import { useState } from "react";

import { Cycle, PLAN_ORDER, Plan, VIDEO_DURATIONS, VIDEO_RESOLUTIONS, num, money, perMonth, usePricing } from "../../lib/plans";
import { useSession } from "../../lib/session";

const PITCH: Record<string, string> = {
  baslangic: "Kendi işletmesinin hesabını yöneten esnaf için.",
  pro: "Düzenli paylaşım yapan ve reklam veren işletmeler için.",
  ajans: "Birden fazla markayı yöneten ajans ve danışmanlar için.",
};

/** Krediyi gerçekçi bir aya bölen örnek: biraz fikir, çoğu görsel ve video. */
function sampleMonth(p: Plan, c: CreditCosts) {
  const ideaCredits = Math.floor(p.credits * 0.03);
  const ideas = Math.floor(ideaCredits / c.chat_message);
  const images = Math.floor((p.credits * 0.37) / c.image);
  const videos = p.video_enabled ? Math.floor((p.credits - ideaCredits - images * c.image) / c.video["720p"]["5"]) : 0;
  return { ideas, images, videos };
}

export default function Paketler() {
  const pricing = usePricing();
  const { usage, openCheckout } = useSession();
  const plans = pricing?.plans;
  const costs = pricing?.costs;
  const ids = PLAN_ORDER.filter((id) => plans?.[id]);
  const [cycle, setCycle] = useState<Cycle>("monthly");

  return (
    <div className="page">
      <section className="price-hero">
        <h1>İşine uyan paketi seç</h1>
        <p>
          Her paket 30 günlük bir kredi bakiyesi verir. Sohbet, görsel ve video ürettikçe krediden düşer; ne üreteceğine
          sen karar verirsin. Fiyatlara %20 KDV eklenir. Otomatik yenilenmez; ödeme iyzico ile dolar (USD) olarak, kartından güncel kurla alınır.
        </p>
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

      {pricing === null ? (
        <div className="plans">
          {[0, 1, 2].map((i) => (
            <div key={i} className="panel plan" style={{ minHeight: 420 }} />
          ))}
        </div>
      ) : ids.length === 0 || !plans || !costs ? (
        <div className="panel empty" style={{ marginTop: 32 }}>
          <h3>Paketler yüklenemedi</h3>
          <p>Sayfayı yenileyip tekrar dene.</p>
        </div>
      ) : (
        <>
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
                    {money(perMonth(p, cycle), p.currency)} <small>/ ay + KDV</small>
                  </div>
                  <p className="plan-sub" style={{ marginTop: -6 }}>
                    {cycle === "yearly" ? `Yıllık ${money(p.price_yearly, p.currency)} + KDV tek ödeme` : "30 gün geçerli"}
                  </p>
                  <div className="credit-badge">
                    <strong>{num(p.credits)}</strong> kredi / ay
                  </div>
                  <p className="plan-sub">Bu krediyle yalnızca birini yaparsan:</p>
                  <ul>
                    <li>{num(p.examples.messages)} sohbet mesajı</li>
                    <li>{num(p.examples.images)} görsel</li>
                    <li>
                      5 sn video: {num(p.examples.videos["720p"])} adet 720p, {num(p.examples.videos["1080p"])} adet 1080p ya da {num(p.examples.videos["4k"])} adet 4K
                    </li>
                    <li className={p.ads_enabled ? "" : "no"}>Instagram reklam taslağı (Meta){p.ads_enabled ? ", kredi harcamaz" : ""}</li>
                  </ul>
                  <button
                    className={`btn btn-block ${id === "pro" ? "btn-primary" : "btn-light"}`}
                    onClick={() => openCheckout(`${id}:${cycle}`)}
                  >
                    {current ? "30 gün uzat" : `${p.name} paketini al`}
                  </button>
                </article>
              );
            })}
          </div>

          {pricing.free && (
            <section className="panel free-plan">
              <div>
                <h3>Ücretsiz paket</h3>
                <p className="muted">
                  Kayıt olan herkes bununla başlar, kart gerekmez. Üye olmadan da{" "}
                  <a href="/ucretsiz">deneyebilirsin</a> (günde {pricing.free.chat_per_day_guest} mesaj).
                </p>
              </div>
              <ul>
                <li>Günde {pricing.free.chat_per_day} sohbet mesajı (yalnızca metin)</li>
                <li>30 günde {pricing.free.images_per_month} ücretsiz AI görseli</li>
                <li>Sınırsız telifsiz stok fotoğraf</li>
              </ul>
            </section>
          )}

          <section className="section">
            <div className="section-head">
              <div>
                <h2>Hangi işlem kaç kredi?</h2>
                <p>Üretim başarısız olursa harcanan kredi otomatik olarak iade edilir.</p>
              </div>
            </div>
            <div className="panel table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>İşlem</th>
                    <th>Kredi</th>
                    <th>Ne alırsın</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Sohbet mesajı</td>
                    <td className="num">
                      Mesaj başı {costs.chat_message}, her ek +{costs.chat_attachment}
                    </td>
                    <td>
                      Fikir, caption, hashtag ve reklam metni; fotoğraf, video ve belge ekleyerek örnek üzerinden çalışır.{" "}
                      {costs.chat_pdf_pages ?? 10} sayfadan uzun PDF'lerde her {costs.chat_pdf_pages ?? 10} sayfa +1 kredi (en fazla 60 sayfa).
                    </td>
                  </tr>
                  <tr>
                    <td>Örnekten konsept</td>
                    <td className="num">{costs.describe}</td>
                    <td>Yüklediğin görsel veya videoya bakıp aynı tarzda yeni görsel/video için konsept yazar</td>
                  </tr>
                  <tr>
                    <td>Görsel</td>
                    <td className="num">{costs.image}</td>
                    <td>Kare, hikâye, gönderi veya yatay formatta bir görsel; 4 adede kadar ürün/stil görseli örnek alabilir</td>
                  </tr>
                  <tr>
                    <td>Video</td>
                    <td className="num">{costs.video["720p"]["5"]}–{num(costs.video["4k"]["10"])}</td>
                    <td>Reels ve hikâye için dikey video; süre ve çözünürlüğe göre, aşağıdaki tabloya bak</td>
                  </tr>
                  <tr>
                    <td>Meta reklam taslağı</td>
                    <td className="num">{costs.ads_draft === 0 ? "Ücretsiz" : costs.ads_draft}</td>
                    <td>Instagram için duraklatılmış kampanya taslağı (Pro ve Advanced)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2>Video kredi tablosu</h2>
                <p>Metinden veya görselden (başlangıç ve bitiş karesi), 9:16, 1:1 veya 16:9. Parantez içi sesli fiyattır.</p>
              </div>
            </div>
            <div className="panel table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Çözünürlük</th>
                    {VIDEO_DURATIONS.map((d) => (
                      <th key={d}>{d} saniye</th>
                    ))}
                    <th>Ne zaman seçilir</th>
                  </tr>
                </thead>
                <tbody>
                  {VIDEO_RESOLUTIONS.map((r) => (
                    <tr key={r.value}>
                      <td>{r.label}</td>
                      {VIDEO_DURATIONS.map((d) => (
                        <td key={d} className="num">
                          {num(costs.video[r.value][String(d)])} kredi
                          {costs.video_audio[r.value][String(d)] !== costs.video[r.value][String(d)] && (
                            <span className="faint"> ({num(costs.video_audio[r.value][String(d)])})</span>
                          )}
                        </td>
                      ))}
                      <td className="muted">
                        {r.value === "720p"
                          ? "Instagram Reels ve hikâye için yeterli, en ekonomik"
                          : r.value === "1080p"
                            ? "Daha net görüntü, reklam videoları için"
                            : "Ekran, mağaza içi tabela ve sinema kalitesi gereken işler"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2>Örnek bir ay</h2>
                <p>Krediyi karışık kullanan bir işletmenin bir ayda üretebileceği içerik.</p>
              </div>
            </div>
            <div className="stats">
              {ids.map((id) => {
                const m = sampleMonth(plans[id], costs);
                return (
                  <div key={id} className="panel stat">
                    <div className="name">{plans[id].name}</div>
                    <div className="value" style={{ fontSize: 22 }}>
                      {m.ideas} sohbet mesajı · {m.images} görsel · {m.videos} video (720p, 5 sn)
                    </div>
                    <div className="foot">{num(plans[id].credits)} kredinin karşılığı</div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2>Paketleri karşılaştır</h2>
              </div>
            </div>
            <div className="panel table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th></th>
                    {pricing.trial && <th>Ücretsiz</th>}
                    {ids.map((id) => (
                      <th key={id}>{plans[id].name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Aylık fiyat (+KDV)", (p: Plan) => (p.price ? money(p.price, p.currency) : "Ücretsiz")],
                    ["Yıllık fiyat (+KDV, %20 indirimli)", (p: Plan) => (p.price ? money(p.price_yearly, p.currency) : "—")],
                    ["Kredi", (p: Plan) => (p.credits ? num(p.credits) : "—")],
                    ["Sohbet mesajı (yalnızca)", (p: Plan) => (p.credits ? num(p.examples.messages) : `Günde ${pricing.free?.chat_per_day ?? 20}`)],
                    ["Dosya ekleyerek sohbet", (p: Plan) => (p.credits ? "Var" : "—")],
                    ["Seedream görsel (yalnızca)", (p: Plan) => (p.credits ? num(p.examples.images) : "—")],
                    ["Ücretsiz AI görseli (30 gün)", () => String(pricing.free?.images_per_month ?? 6)],
                    ["Stok fotoğraf", () => "Sınırsız"],
                    ["5 sn 720p video (yalnızca)", (p: Plan) => (p.video_enabled ? num(p.examples.videos["720p"]) : "—")],
                    ["5 sn 1080p video (yalnızca)", (p: Plan) => (p.video_enabled ? num(p.examples.videos["1080p"]) : "—")],
                    ["5 sn 4K video (yalnızca)", (p: Plan) => (p.video_enabled ? num(p.examples.videos["4k"]) : "—")],
                    ["Meta reklam taslağı", (p: Plan) => (p.ads_enabled ? "Var" : "—")],
                  ].map(([label, fn]) => {
                    const f = fn as (p: Plan) => string;
                    return (
                      <tr key={label as string}>
                        <td>{label as string}</td>
                        {pricing.trial && <td className="num">{f(pricing.trial)}</td>}
                        {ids.map((id) => (
                          <td key={id} className="num">
                            {f(plans[id])}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2>Sık sorulanlar</h2>
              </div>
            </div>
            <div className="faq">
              <div className="panel">
                <h3>Krediler bir sonraki aya devreder mi?</h3>
                <p>Hayır. Kredi paketin 30 günü boyunca geçerlidir; paketi yenilediğinde bakiye yeniden dolar.</p>
              </div>
              <div className="panel">
                <h3>Üretim başarısız olursa ne olur?</h3>
                <p>Görsel ya da video üretilemezse harcanan kredi otomatik iade edilir. İadeyi kullanım sayfasında görebilirsin.</p>
              </div>
              <div className="panel">
                <h3>Reklam bütçesi krediden mi düşer?</h3>
                <p>Hayır. Meta reklam bütçesi kendi Meta hesabından harcanır; ajansAI'da taslak oluşturmak kredi harcamaz.</p>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
