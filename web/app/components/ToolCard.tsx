import Link from "next/link";

import { Tool } from "../lib/tools";
import Poster from "./Poster";

export default function ToolCard({ tool }: { tool: Tool }) {
  const inner = (
    <>
      <Poster tool={tool} />
      <div className="body">
        <h3>{tool.name}</h3>
        <p>{tool.short}</p>
        <div className="foot">
          <span className="chip">{tool.costLabel}</span>
          {tool.plan && tool.ready && <span className="chip chip-soft">{tool.plan} ve üzeri</span>}
        </div>
      </div>
    </>
  );

  return (
    <Link href={tool.slug === "fikir" ? "/" : `/araclar/${tool.slug}`} className="tool-card">
      {inner}
    </Link>
  );
}
