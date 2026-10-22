import { KIND_LABEL, Tool } from "../lib/tools";

// Her araç için logodaki indigo kareden türetilen geometrik kapak.
export default function Poster({ tool, showTag = true }: { tool: Tool; showTag?: boolean }) {
  return (
    <div className={`poster poster-${tool.slug}`} aria-hidden="true">
      {showTag && (
        <span className={`chip tag chip-indigo`}>
          {KIND_LABEL[tool.kind]}
        </span>
      )}
      <Art slug={tool.slug} />
    </div>
  );
}

function Art({ slug }: { slug: string }) {
  switch (slug) {
    case "fikir":
      return (
        <div className="grid">
          {Array.from({ length: 21 }).map((_, i) => (
            <span key={i} className={i === 10 ? "on" : ""} />
          ))}
        </div>
      );
    case "gorsel":
      return (
        <>
          <i className="sq" />
          <i className="frame" />
        </>
      );
    case "video":
      return (
        <>
          <div className="strip">
            {Array.from({ length: 6 }).map((_, i) => (
              <span key={i} />
            ))}
          </div>
          <i className="play" />
        </>
      );
    case "reklam":
      return (
        <>
          <i className="ring r1" />
          <i className="ring r2" />
          <i className="ring r3" />
        </>
      );
    default:
      return null;
  }
}
