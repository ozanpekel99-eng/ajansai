"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getChat, isShownChat, setShownChat } from "../lib/chats";
import type { Conversation } from "../components/ChatPanel";
import FikirWorkspace from "../components/workspaces/Fikir";

/** Ana sayfa: Claude / ChatGPT gibi doğrudan sohbet. Geçmiş sohbetler sol menüde. */
function ChatHome() {
  const params = useSearchParams();
  const id = params.get("c");
  const fresh = params.get("yeni");
  const [chat, setChat] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(!!id);
  // Yeni sohbet anahtarı: adres çubuğu ?c= ile güncellenince ekrandaki sohbet yeniden kurulmasın
  const freshKey = useRef(fresh || "0");
  if (fresh && fresh !== freshKey.current) freshKey.current = fresh;

  useEffect(() => {
    let alive = true;
    if (!id) {
      setShownChat(null);
      setChat(null);
      setLoading(false);
      return;
    }
    // Bu sekmede az önce başlatılan sohbet zaten ekranda: yeniden yükleme
    if (chat?.id === id || isShownChat(id)) return;
    setLoading(true);
    getChat(id).then((c) => {
      if (!alive) return;
      setShownChat(c?.id ?? null);
      setChat(c);
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return null;
  return <FikirWorkspace key={chat?.id ?? `yeni-${freshKey.current}`} initial={chat} />;
}

export default function Home() {
  return (
    <div className="page chat-page">
      <Suspense fallback={null}>
        <ChatHome />
      </Suspense>
    </div>
  );
}
