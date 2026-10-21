"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ApiError, api } from "../../lib/api";
import { HistoryEntry, addHistory, readHistory } from "../../lib/history";
import { useSession } from "../../lib/session";
import { EmptyResult, HistoryList, LockedNotice, RemainingLine, WorkspaceProps } from "./common";

const RATIOS = [
  { value: "ASPECT_1_1", label: "Kare 1:1" },
  { value: "ASPECT_9_16", label: "Hikâye 9:16" },
  { value: "ASPECT_3_4", label: "Gönderi 3:4" },
  { value: "ASPECT_16_9", label: "Yatay 16:9" },
];

type Result = { url: string; concept: string };

export default function GorselWorkspace({ tab, showCreate }: WorkspaceProps) {
  const params = useSearchParams();
  const { usage, refresh } = useSession();
  const [concept, setConcept] = useState(params.get("konsept") || "");
  const [ratio, setRatio] = useState("ASPECT_1_1");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<HistoryEntry<Result>[]>([]);

  useEffect(() => setHistory(readHistory<Result>("gorsel")), []);

  const locked = usage?.image.quota === 0;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ image_url: string | null; error: string | null }>("/api/content/image", {
        method: "POST",
        body: JSON.stringify({ concept, aspect_ratio: ratio }),
      });
      if (!data.image_url) {
        setError(`${data.error || "Görsel üretilemedi."} Hakkın iade edildi.`);
      } else {
        const r = { url: data.image_url, concept };
        setResult(r);
        addHistory("gorsel", concept.slice(0, 80), r);
        setHistory(readHistory("gorsel"));
      }
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setLoading(false);
      refresh();
    }
  };

  if (tab === "history") {
    return <HistoryList items={history} onOpen={(item) => {
          setResult(item.data);
          showCreate();
        }} />;
  }

  return (
    <div className="workspace">
      <form className="panel ws-panel" onSubmit={submit}>
        <h2>Görsel ayarları</h2>
        {locked && <LockedNotice text="Görsel üretimi Başlangıç ve üzeri paketlerde açılır." />}
        <div className="field">
          <label htmlFor="g-concept">Konsept</label>
          <textarea
            id="g-concept"
            required
            rows={5}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="Beyaz mutfakta yeni nesil gri buzdolabı, sabah ışığı, ön planda taze meyveler"
          />
          <span className="hint">Ne görünmesini istediğini, ışığı ve ortamı yaz. Yazı içeren görsellerde metni tırnak içinde ver.</span>
        </div>
        <div className="field">
          <label>Format</label>
          <div className="segmented">
            {RATIOS.map((r) => (
              <button type="button" key={r.value} className={ratio === r.value ? "active" : ""} onClick={() => setRatio(r.value)} aria-pressed={ratio === r.value}>
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <div className="generate">
          <button className="btn btn-primary btn-block" type="submit" disabled={loading || locked}>
            {loading ? "Görsel üretiliyor…" : "Görsel üret"}
          </button>
          <RemainingLine kind="image" />
        </div>
      </form>

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>
          Sonuç
          {result && (
            <span style={{ display: "flex", gap: 6 }}>
              <a className="btn btn-ghost btn-sm" href={result.url} target="_blank" rel="noreferrer">
                İndir
              </a>
              <Link
                className="btn btn-ghost btn-sm"
                href={`/araclar/video?konsept=${encodeURIComponent(result.concept)}&gorsel=${encodeURIComponent(result.url)}`}
              >
                Videoya çevir
              </Link>
            </span>
          )}
        </h2>
        {error && <div className="notice error">{error}</div>}
        {loading ? (
          <EmptyResult loading text="Görsel üretiliyor, genelde 10–30 saniye sürer." />
        ) : result ? (
          <div className="media-result">
            <img src={result.url} alt={result.concept} />
          </div>
        ) : (
          <EmptyResult text="Konseptini yaz ve formatı seç, görsel burada görünecek." />
        )}
      </section>
    </div>
  );
}
