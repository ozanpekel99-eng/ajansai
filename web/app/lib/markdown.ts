// Asistan yanıtları için küçük ve güvenli markdown çevirici: önce HTML kaçırılır,
// sonra başlık, kalın/italik, liste ve satır içi kod biçimlenir.

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const inline = (s: string) =>
  esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");

export function renderMarkdown(src: string): string {
  const out: string[] = [];
  let list: "ul" | "ol" | null = null;
  const close = () => {
    if (list) out.push(`</${list}>`);
    list = null;
  };

  for (const raw of src.replace(/\r/g, "").split("\n")) {
    const line = raw.trimEnd();
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    const ul = line.match(/^\s*[-*•]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (h) {
      close();
      const level = Math.min(h[1].length + 2, 5);
      out.push(`<h${level}>${inline(h[2])}</h${level}>`);
    } else if (ul || ol) {
      const kind = ul ? "ul" : "ol";
      if (list !== kind) {
        close();
        out.push(`<${kind}>`);
        list = kind;
      }
      out.push(`<li>${inline((ul || ol)![1])}</li>`);
    } else if (/^\s*(---|\*\*\*)\s*$/.test(line)) {
      close();
      out.push("<hr/>");
    } else if (!line.trim()) {
      close();
    } else {
      close();
      out.push(`<p>${inline(line)}</p>`);
    }
  }
  close();
  return out.join("");
}

/** Yanıttaki "Görsel konsepti:" / "Video konsepti:" satırını bulur. */
export function extractConcept(src: string, kind: "Görsel" | "Video"): string | null {
  const re = new RegExp(`${kind}(?:/Video|/Görsel)?\\s*konsepti\\s*:\\s*\\**\\s*(.+)`, "i");
  const m = src.match(re);
  return m ? m[1].replace(/\*+/g, "").trim() : null;
}
