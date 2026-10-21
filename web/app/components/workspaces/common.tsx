"use client";

import Link from "next/link";

import { HistoryEntry, timeAgo } from "../../lib/history";
import { useSession } from "../../lib/session";

export type WorkspaceProps = { tab: "create" | "history"; showCreate: () => void };

/** Üret düğmesinin altındaki "kalan hak" satırı. */
export function RemainingLine({ kind }: { kind: "ideas" | "image" | "video" }) {
  const { usage } = useSession();
  if (!usage) return null;
  const q = usage[kind];
  const label = kind === "ideas" ? "fikir" : kind === "image" ? "görsel" : "video";
  if (q.quota === null) return <div className="cost"><span>Bu ay sınırsız {label}</span><span>{usage.plan_name}</span></div>;
  return (
    <div className="cost">
      <span>
        Bu ay {Math.max(q.quota - q.used, 0)} / {q.quota} {label} hakkın kaldı
      </span>
      <span>{usage.plan_name}</span>
    </div>
  );
}

/** Paketi bu aracı kapsamıyorsa üretim yerine gösterilir. */
export function LockedNotice({ text, plan = "baslangic" }: { text: string; plan?: string }) {
  const { openCheckout } = useSession();
  return (
    <div className="notice">
      <span>{text}</span>
      <button className="btn btn-light btn-sm" onClick={() => openCheckout(plan)}>
        Paket seç
      </button>
    </div>
  );
}

export function EmptyResult({ loading, text }: { loading?: boolean; text: string }) {
  return (
    <div className="result-empty">
      <div>
        <div className={`mark ${loading ? "loading-mark" : ""}`} />
        {text}
      </div>
    </div>
  );
}

export function HistoryList<T>({
  items,
  onOpen,
}: {
  items: HistoryEntry<T>[];
  onOpen: (item: HistoryEntry<T>) => void;
}) {
  if (!items.length) {
    return (
      <div className="panel empty">
        <h3>Henüz bir şey üretmedin</h3>
        <p>
          Oluştur sekmesinden ilk üretimini yap; sonuçlar burada listelenir. Geçmiş bu tarayıcıda saklanır.
        </p>
      </div>
    );
  }
  return (
    <div className="history">
      {items.map((item) => (
        <button key={item.id} className="history-item" onClick={() => onOpen(item)} style={{ textAlign: "left", cursor: "pointer", color: "inherit" }}>
          <span>{item.title}</span>
          <span className="when">{timeAgo(item.at)}</span>
        </button>
      ))}
    </div>
  );
}

export function UpgradeLink() {
  return (
    <Link href="/paketler" className="btn btn-ghost btn-sm">
      Paketleri karşılaştır
    </Link>
  );
}
