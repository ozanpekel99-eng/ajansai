"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "../lib/api";
import { useSession } from "../lib/session";
import { PendingFile, UploadProgress, useUploader } from "./Attachments";
import Icon from "./Icon";

/** Higgsfield tarzı ayar çipi: tıklayınca seçenek listesi açılır, her seçenekte not (ör. kredi) gösterilir. */
export function ChipSelect<T extends string | number>({
  icon,
  label,
  value,
  options,
  onChange,
}: {
  icon: string;
  label: string;
  value: T;
  options: { value: T; label: string; note?: string }[];
  onChange: (v: T) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: globalThis.KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div className="chip-select" ref={ref}>
      <button type="button" aria-haspopup="listbox" aria-expanded={open} aria-label={label} onClick={() => setOpen((o) => !o)}>
        <Icon name={icon} size={15} />
        {current?.label}
      </button>
      {open && (
        <ul role="listbox" aria-label={label}>
          {options.map((o) => (
            <li key={String(o.value)}>
              <button
                type="button"
                role="option"
                aria-selected={o.value === value}
                className={o.value === value ? "active" : ""}
                onClick={() => {
                  onChange(o.value);
                  setOpen(false);
                }}
              >
                <span>{o.label}</span>
                {o.note && <small>{o.note}</small>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Toggle({ label, checked, onChange, note }: { label: string; checked: boolean; onChange: (v: boolean) => void; note?: string }) {
  return (
    <label className="toggle-row">
      <span>
        {label}
        {note && <small>{note}</small>}
      </span>
      <input type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="switch" aria-hidden="true" />
    </label>
  );
}

/** Tek görsellik yükleme kutusu (başlangıç / bitiş karesi gibi). */
export function ImageSlot({
  label,
  required,
  url,
  onChange,
}: {
  label: string;
  required?: boolean;
  url: string;
  onChange: (url: string) => void;
}) {
  const up = useUploader(["image"], 1, 0, (f) => onChange(f.url));
  return (
    <div className="image-slot">
      {up.field}
      {url ? (
        <div className="filled">
          <img src={url} alt={label} />
          <button type="button" aria-label={`${label} kaldır`} onClick={() => onChange("")}>
            <Icon name="close" size={14} />
          </button>
        </div>
      ) : (
        <button type="button" className="empty-slot" onClick={up.pick} disabled={up.busy.length > 0}>
          <Icon name="image" />
          <span>
            {up.busy.length ? `Yükleniyor %${up.busy[0].pct}` : label}
            {required && <em aria-hidden="true"> *</em>}
          </span>
        </button>
      )}
      {up.error && <small className="error-text">{up.error}</small>}
    </div>
  );
}

/** Örnek görsel/video yükle → yapay zeka aynı tarzda yeni üretim için konsept yazar. */
export function SampleToConcept({ target, onConcept }: { target: "image" | "video"; onConcept: (text: string) => void }) {
  const { usage, refresh } = useSession();
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [sample, setSample] = useState<PendingFile | null>(null);
  const cost = usage?.costs.describe ?? 1;

  const run = async (file: PendingFile) => {
    setSample(file);
    setWorking(true);
    setError("");
    try {
      const data = await api<{ concept: string }>("/api/content/describe", {
        method: "POST",
        body: JSON.stringify({ attachment: { url: file.url, content_type: file.content_type, name: file.name }, target }),
      });
      onConcept(data.concept);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setWorking(false);
      refresh();
    }
  };

  const up = useUploader(["image", "video"], 1, 0, run);

  return (
    <div className="sample-row">
      {up.field}
      <button type="button" className="link-btn" onClick={up.pick} disabled={working || up.busy.length > 0}>
        <Icon name="sparkle" size={14} />
        {working ? "Örnek inceleniyor…" : `Örnek görsel/videodan konsept yaz · ${cost} kredi`}
      </button>
      {sample && !working && !error && <small className="faint">“{sample.name}” örneğine göre yazıldı</small>}
      <UploadProgress busy={up.busy} />
      {(error || up.error) && <small className="error-text">{error || up.error}</small>}
    </div>
  );
}
