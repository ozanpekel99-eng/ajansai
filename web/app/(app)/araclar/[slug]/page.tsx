"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import Poster from "../../../components/Poster";
import FikirWorkspace from "../../../components/workspaces/Fikir";
import GorselWorkspace from "../../../components/workspaces/Gorsel";
import ReklamWorkspace from "../../../components/workspaces/Reklam";
import VideoWorkspace from "../../../components/workspaces/Video";
import { WorkspaceProps } from "../../../components/workspaces/common";
import { KIND_LABEL, getTool } from "../../../lib/tools";

const WORKSPACES: Record<string, React.ComponentType<WorkspaceProps>> = {
  fikir: FikirWorkspace,
  gorsel: GorselWorkspace,
  video: VideoWorkspace,
  reklam: ReklamWorkspace,
};

export default function ToolPage() {
  const params = useParams<{ slug: string }>();
  const tool = getTool(params.slug);
  const [tab, setTab] = useState<"create" | "history">("create");

  if (!tool || !tool.ready || !WORKSPACES[tool.slug]) {
    return (
      <div className="page">
        <div className="panel empty">
          <h3>Bu araç bulunamadı</h3>
          <p>Şimdilik diğer araçları kullanabilirsin.</p>
          <p>
            <Link href="/araclar" className="btn btn-ghost btn-sm">
              Araçlara dön
            </Link>
          </p>
        </div>
      </div>
    );
  }

  const Workspace = WORKSPACES[tool.slug];

  // Sohbet artık ana sayfada
  if (tool.slug === "fikir") {
    if (typeof window !== "undefined") window.location.replace("/" + window.location.search);
    return (
      <div className="page chat-page">
        <div className="chat-page-bar">
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => setTab(tab === "history" ? "create" : "history")}>
            {tab === "history" ? "Sohbete dön" : "Geçmiş sohbetler"}
          </button>
        </div>
        <Suspense fallback={null}>
          <Workspace tab={tab} showCreate={() => setTab("create")} />
        </Suspense>
      </div>
    );
  }
  const hasHistory = tool.slug !== "reklam";

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Konum">
        <Link href="/araclar">Araçlar</Link>
        <span>/</span>
        <strong>{tool.name}</strong>
      </nav>

      <header className="tool-head">
        <div>
          <div className="badges">
            <span className="chip chip-indigo">{KIND_LABEL[tool.kind]}</span>
            <span className="chip">{tool.costLabel}</span>
            {tool.plan && <span className="chip chip-soft">{tool.plan} ve üzeri</span>}
          </div>
          <h1>{tool.name}</h1>
          <p>{tool.long}</p>
        </div>
        <Poster tool={tool} showTag={false} />
      </header>

      {hasHistory ? (
        <div className="underline-tabs" role="tablist">
          <button role="tab" aria-selected={tab === "create"} className={tab === "create" ? "active" : ""} onClick={() => setTab("create")}>
            Oluştur
          </button>
          <button role="tab" aria-selected={tab === "history"} className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>
            Geçmiş
          </button>
        </div>
      ) : (
        <div className="underline-tabs" />
      )}

      <Suspense fallback={null}>
        <Workspace tab={tab} showCreate={() => setTab("create")} />
      </Suspense>
    </div>
  );
}
