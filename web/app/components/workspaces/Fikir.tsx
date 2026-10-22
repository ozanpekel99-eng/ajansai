"use client";

import { useEffect, useState } from "react";

import { HistoryEntry } from "../../lib/history";
import { useFreeStatus } from "../../lib/free";
import { useSession } from "../../lib/session";
import ChatPanel, { Conversation, loadChats } from "../ChatPanel";
import { LockedNotice, NoCreditsNotice, WorkspaceProps } from "./common";

export default function FikirWorkspace({ tab, showCreate }: WorkspaceProps) {
  const { usage, refresh } = useSession();
  const { status, setStatus } = useFreeStatus();
  const [chats, setChats] = useState<Conversation[]>([]);
  const [open, setOpen] = useState<Conversation | null>(null);

  useEffect(() => setChats(loadChats()), [tab]);

  if (tab === "history") {
    const items: HistoryEntry<Conversation>[] = chats.map((c) => ({ id: c.id, title: c.title, at: c.at, data: c }));
    if (!items.length) {
      return (
        <div className="panel empty">
          <h3>Henüz sohbet yok</h3>
          <p>Oluştur sekmesinden ilk mesajını yaz; sohbetlerin burada listelenir. Geçmiş bu tarayıcıda saklanır.</p>
        </div>
      );
    }
    return (
      <div className="history">
        {items.map((item) => (
          <button
            key={item.id}
            className="history-item"
            style={{ textAlign: "left", cursor: "pointer", color: "inherit" }}
            onClick={() => {
              setOpen(item.data);
              showCreate();
            }}
          >
            <span>{item.title}</span>
            <span className="when">{new Date(item.at).toLocaleDateString("tr-TR")}</span>
          </button>
        ))}
      </div>
    );
  }

  if (!usage) return null;

  const conceptHref = (kind: "gorsel" | "video", concept: string) =>
    `/araclar/${kind}?konsept=${encodeURIComponent(concept)}`;

  // Ücretsiz paket: Haiku ile kredisiz sohbet, günlük mesaj hakkı, dosya eklenemez.
  if (usage.plan === "deneme") {
    const left = status?.chat.remaining;
    return (
      <ChatPanel
        key={open?.id ?? "yeni"}
        initial={open}
        endpoint="/api/free/chat"
        allowFiles={false}
        conceptHref={conceptHref}
        onSent={(data) => data?.free && setStatus(data.free)}
        blocker={
          left === 0 ? (
            <LockedNotice text={`Bugünkü ${status?.chat.limit} ücretsiz mesaj hakkın doldu. Yarın devam edebilir ya da bir paketle sınırsız yazabilirsin.`} />
          ) : undefined
        }
        footer={() =>
          status
            ? `Ücretsiz paket · bugün ${status.chat.remaining}/${status.chat.limit} mesaj hakkın var · fotoğraf, video ve belge eklemek için paket seç`
            : "Ücretsiz paket"
        }
      />
    );
  }

  const costs = usage.costs;
  const lacking = usage.credits.remaining < costs.chat_message;
  return (
    <ChatPanel
      key={open?.id ?? "yeni"}
      initial={open}
      endpoint="/api/content/chat"
      allowFiles
      conceptHref={conceptHref}
      onSent={() => refresh()}
      blocker={lacking ? <NoCreditsNotice cost={costs.chat_message} /> : undefined}
      footer={(files) => {
        const cost = costs.chat_message + files * costs.chat_attachment;
        return `Bu mesaj ${cost} kredi${files ? ` (mesaj 1 + ${files} dosya; ${costs.chat_pdf_pages ?? 10} sayfadan uzun PDF'lerde her ${costs.chat_pdf_pages ?? 10} sayfa +1)` : ""} · Enter gönderir, Shift+Enter alt satır`;
      }}
    />
  );
}
