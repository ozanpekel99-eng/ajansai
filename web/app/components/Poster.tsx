import { KIND_LABEL, Tool } from "../lib/tools";

// Her araç için logodaki indigo kareden türetilen geometrik kapak.
export default function Poster({ tool, showTag = true }: { tool: Tool; showTag?: boolean }) {
  return (
    <div className={`poster poster-${tool.slug}`} aria-hidden="true">
      {showTag && (
        <span className={`chip tag ${tool.ready ? "chip-indigo" : "chip-muted"}`}>
          {tool.ready ? KIND_LABEL[tool.kind] : "Yakında"}
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
    case "caption":
      return (
        <div className="lines">
          <span />
          <span />
          <span />
          <span />
        </div>
      );
    case "hashtag":
      return <b>#</b>;
    case "takvim":
      return (
        <div className="cal">
          {Array.from({ length: 28 }).map((_, i) => (
            <span key={i} className={i === 11 || i === 19 ? "on" : ""} />
          ))}
        </div>
      );
    case "reklam-metni":
      return (
        <>
          <i className="bubble" />
          <i className="tail" />
          <i className="bar" />
        </>
      );
    default:
      return null;
  }
}
