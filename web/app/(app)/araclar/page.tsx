"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import Icon from "../../components/Icon";
import Poster from "../../components/Poster";
import ToolCard from "../../components/ToolCard";
import { useSession } from "../../lib/session";
import { KIND_LABEL, READY_TOOLS, TOOLS, ToolKind } from "../../lib/tools";

const FILTERS: { key: "all" | ToolKind; label: string }[] = [
  { key: "all", label: "Tümü" },
  { key: "metin", label: "Metin" },
  { key: "gorsel", label: "Görsel" },
  { key: "video", label: "Video" },
  { key: "reklam", label: "Reklam" },
];

export default function Tools() {
  const { usage, openCheckout } = useSession();
  const [featured, setFeatured] = useState(0);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const [query, setQuery] = useState("");

  const hero = READY_TOOLS[featured];
  const list = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("tr");
    return TOOLS.filter((t) => (filter === "all" || t.kind === filter))
      .filter((t) => !q || `${t.name} ${t.short}`.toLocaleLowerCase("tr").includes(q))
      .sort((a, b) => Number(b.ready) - Number(a.ready));
  }, [filter, query]);

  return (
    <div className="page">
      <section className="hero" aria-label="Öne çıkan araç">
        <div className="hero-copy">
          <div>
            <span className="chip chip-indigo">{KIND_LABEL[hero.kind]}</span>
          </div>
          <h1>{hero.name}</h1>
          <p>{hero.long}</p>
          <div className="row">
            <Link href={`/araclar/${hero.slug}`} className="btn btn-light">
              Aracı aç
            </Link>
            <span className="muted">{hero.costLabel}</span>
          </div>
        </div>
        <Poster tool={hero} showTag={false} />
        <div className="hero-thumbs" role="tablist" aria-label="Öne çıkan araçlar">
          {READY_TOOLS.map((t, i) => (
            <button
              key={t.slug}
              role="tab"
              aria-selected={i === featured}
              aria-label={t.name}
              className={i === featured ? "active" : ""}
              onClick={() => setFeatured(i)}
            >
              <Poster tool={t} showTag={false} />
            </button>
          ))}
        </div>
      </section>

      {usage?.plan === "deneme" && (
        <div className="section promo">
          <span className="promo-icon">
            <Icon name="gift" size={20} />
          </span>
          <div>
            <h3>Pro ile reklam kampanyaları da burada</h3>
            <p>800 kredi ve Meta reklam entegrasyonu: örneğin 200 görsel ya da 66 kısa video.</p>
          </div>
          <button className="btn btn-light" onClick={() => openCheckout("pro")}>
            Pro'ya geç
          </button>
        </div>
      )}

      <section className="section">
        <div className="filters">
          <div className="tabs" role="tablist" aria-label="Araç türü">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                role="tab"
                aria-selected={filter === f.key}
                className={filter === f.key ? "active" : ""}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <label className="search">
            <Icon name="search" size={16} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Araç ara" aria-label="Araç ara" />
          </label>
        </div>

        {list.length ? (
          <div className="tool-grid">
            {list.map((t) => (
              <ToolCard key={t.slug} tool={t} />
            ))}
          </div>
        ) : (
          <div className="panel empty">
            <h3>"{query}" ile eşleşen araç yok</h3>
            <p>Farklı bir kelime dene ya da filtreyi Tümü yap.</p>
          </div>
        )}
      </section>
    </div>
  );
}
