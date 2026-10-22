"use client";

import { Suspense, useState } from "react";

import FikirWorkspace from "../components/workspaces/Fikir";

/** Ana sayfa: ChatGPT gibi doğrudan sohbet. Araçlar sol menüde ve + menüsünde. */
export default function Home() {
  const [tab, setTab] = useState<"create" | "history">("create");
  return (
    <div className="page chat-page">
      <div className="chat-page-bar">
        <button className="btn btn-ghost btn-sm" type="button" onClick={() => setTab(tab === "history" ? "create" : "history")}>
          {tab === "history" ? "Sohbete dön" : "Geçmiş sohbetler"}
        </button>
      </div>
      <Suspense fallback={null}>
        <FikirWorkspace tab={tab} showCreate={() => setTab("create")} />
      </Suspense>
    </div>
  );
}
