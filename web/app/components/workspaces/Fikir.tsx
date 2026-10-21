"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, api } from "../../lib/api";
import { HistoryEntry, addHistory, readHistory } from "../../lib/history";
import { useSession } from "../../lib/session";
import { ideaCredits } from "../../lib/plans";
import { CreditLine, EmptyResult, HistoryList, LockedNotice, NoCreditsNotice, WorkspaceProps } from "./common";

type Idea = {
  platform: string;
  format: string;
  title: string;
  concept: string;
  caption: string;
  hashtags: string[];
};

const FORM_KEY = "ajansai_idea_form";
const EMPTY = { business_name: "", sector: "", target_audience: "", tone: "", topic: "" };

export default function FikirWorkspace({ tab, showCreate }: WorkspaceProps) {
  const { usage, refresh } = useSession();
  const [form, setForm] = useState(EMPTY);
  const [count, setCount] = useState(4);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [quotaHit, setQuotaHit] = useState(false);
  const [history, setHistory] = useState<HistoryEntry<Idea[]>[]>([]);
  const [copied, setCopied] = useState<number | null>(null);

  useEffect(() => {
    // İşletme bilgilerini her seferinde tekrar yazdırmamak için son formu hatırla
    try {
      setForm({ ...EMPTY, ...JSON.parse(localStorage.getItem(FORM_KEY) || "{}"), topic: "" });
    } catch {
      // yok say
    }
    setHistory(readHistory<Idea[]>("fikir"));
  }, []);

  const cost = ideaCredits(count, usage?.costs);
  const noCredits = !!usage && usage.credits.remaining < cost;

  const update = (key: keyof typeof EMPTY, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setQuotaHit(false);
    try {
      localStorage.setItem(FORM_KEY, JSON.stringify(form));
    } catch {
      // yok say
    }
    try {
      const data = await api<{ ideas: Idea[]; error?: string }>("/api/content/ideas", {
        method: "POST",
        body: JSON.stringify({ ...form, idea_count: count }),
      });
      if (data.error || !data.ideas?.length) {
        setError("Fikirler oluşturulamadı, kredin iade edildi. Konuyu biraz daha açıp tekrar dene.");
      } else {
        setIdeas(data.ideas);
        addHistory("fikir", `${form.business_name}: ${form.topic}`, data.ideas);
        setHistory(readHistory("fikir"));
      }
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.message);
      setQuotaHit(apiErr.status === 402);
    } finally {
      setLoading(false);
      refresh();
    }
  };

  const copy = async (idea: Idea, i: number) => {
    try {
      await navigator.clipboard.writeText(`${idea.caption}\n\n${(idea.hashtags || []).join(" ")}`);
      setCopied(i);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // pano izni yoksa sessizce geç
    }
  };

  if (tab === "history") {
    return (
      <HistoryList
        items={history}
        onOpen={(item) => {
          setIdeas(item.data);
          showCreate();
        }}
      />
    );
  }

  return (
    <div className="workspace">
      <form className="panel ws-panel" onSubmit={submit}>
        <h2>İşletme bilgileri</h2>
        <NoCreditsNotice cost={cost} />
        <div className="field">
          <label htmlFor="f-name">İşletme adı</label>
          <input id="f-name" required value={form.business_name} onChange={(e) => update("business_name", e.target.value)} placeholder="Başak Beyaz Eşya" />
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="f-sector">Sektör</label>
            <input id="f-sector" required value={form.sector} onChange={(e) => update("sector", e.target.value)} placeholder="Beyaz eşya" />
          </div>
          <div className="field">
            <label htmlFor="f-tone">Marka tonu</label>
            <input id="f-tone" required value={form.tone} onChange={(e) => update("tone", e.target.value)} placeholder="Samimi, güven veren" />
          </div>
        </div>
        <div className="field">
          <label htmlFor="f-audience">Hedef kitle</label>
          <input id="f-audience" required value={form.target_audience} onChange={(e) => update("target_audience", e.target.value)} placeholder="Çorlu'da ev kuran çiftler, 25–45 yaş" />
        </div>
        <div className="field">
          <label htmlFor="f-topic">Bu içerik ne hakkında?</label>
          <textarea id="f-topic" required rows={3} value={form.topic} onChange={(e) => update("topic", e.target.value)} placeholder="Yeni sezon buzdolaplarında peşin fiyatına 6 taksit kampanyası" />
        </div>
        <div className="field">
          <label>Fikir sayısı</label>
          <div className="segmented">
            {[2, 4, 6].map((n) => (
              <button type="button" key={n} className={count === n ? "active" : ""} onClick={() => setCount(n)} aria-pressed={count === n}>
                {n} fikir · {ideaCredits(n, usage?.costs)} kredi
              </button>
            ))}
          </div>
        </div>
        <div className="generate">
          <button className="btn btn-primary btn-block" type="submit" disabled={loading || noCredits}>
            {loading ? "Fikirler hazırlanıyor…" : `Fikir üret · ${cost} kredi`}
          </button>
          <CreditLine cost={cost} />
        </div>
      </form>

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>Sonuç</h2>
        {quotaHit && <LockedNotice text={error} />}
        {error && !quotaHit && <div className="notice error">{error}</div>}
        {loading ? (
          <EmptyResult loading text="Fikirler hazırlanıyor, bu 10–20 saniye sürebilir." />
        ) : ideas.length ? (
          <div className="ideas">
            {ideas.map((idea, i) => (
              <article className="idea" key={i}>
                <div className="meta">
                  <span className="chip chip-soft">{idea.platform}</span>
                  <span className="chip">{idea.format}</span>
                </div>
                <h3>{idea.title}</h3>
                <p>{idea.concept}</p>
                <div className="caption">{idea.caption}</div>
                <div className="tags">{(idea.hashtags || []).join(" ")}</div>
                <div className="actions">
                  <button className="btn btn-ghost btn-sm" type="button" onClick={() => copy(idea, i)}>
                    {copied === i ? "Kopyalandı" : "Caption'ı kopyala"}
                  </button>
                  <Link className="btn btn-ghost btn-sm" href={`/araclar/gorsel?konsept=${encodeURIComponent(idea.concept)}`}>
                    Görsel üret
                  </Link>
                  <Link className="btn btn-ghost btn-sm" href={`/araclar/video?konsept=${encodeURIComponent(idea.concept)}`}>
                    Video üret
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyResult
            text={
              usage?.plan === "deneme"
                ? "Soldaki formu doldur. Deneme paketindeki 20 krediyle fikir ve görsel üretebilirsin."
                : "Soldaki formu doldur, fikirler burada görünecek."
            }
          />
        )}
      </section>
    </div>
  );
}
