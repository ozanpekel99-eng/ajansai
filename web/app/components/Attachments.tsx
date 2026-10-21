"use client";

import { useRef, useState } from "react";

import { ApiError } from "../lib/api";
import { ACCEPT, UploadKind, Uploaded, uploadFile } from "../lib/upload";
import Icon from "./Icon";

export type PendingFile = Uploaded & { id: string };

/** Ataç düğmesi + yükleme. Seçilen dosyaları depoya yükleyip `onAdd` ile bildirir. */
export function useUploader(kinds: UploadKind[], max: number, current: number, onAdd: (f: PendingFile) => void) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<{ name: string; pct: number }[]>([]);
  const [error, setError] = useState("");

  const pick = () => input.current?.click();

  const onChange = async (files: FileList | null) => {
    if (!files) return;
    setError("");
    const list = Array.from(files).slice(0, Math.max(0, max - current));
    if (files.length > list.length) setError(`En fazla ${max} dosya ekleyebilirsin.`);
    await Promise.all(
      list.map(async (file) => {
        setBusy((b) => [...b, { name: file.name, pct: 0 }]);
        try {
          const up = await uploadFile(file, (pct) =>
            setBusy((b) => b.map((x) => (x.name === file.name ? { ...x, pct } : x))),
          );
          onAdd({ ...up, id: `${Date.now()}-${file.name}` });
        } catch (e) {
          setError(e instanceof ApiError ? e.message : `${file.name} yüklenemedi, tekrar dene.`);
        } finally {
          setBusy((b) => b.filter((x) => x.name !== file.name));
        }
      }),
    );
    if (input.current) input.current.value = "";
  };

  const field = (
    <input
      ref={input}
      type="file"
      hidden
      multiple={max > 1}
      accept={kinds.map((k) => ACCEPT[k]).join(",")}
      onChange={(e) => onChange(e.target.files)}
    />
  );

  return { pick, field, busy, error, setError };
}

const KIND_ICON: Record<UploadKind, string> = { image: "Görsel", video: "Video", document: "Belge" };

export function FileChips({ files, onRemove }: { files: PendingFile[]; onRemove?: (id: string) => void }) {
  if (!files.length) return null;
  return (
    <div className="file-chips">
      {files.map((f) => (
        <div key={f.id} className="file-chip">
          {f.kind === "image" ? (
            <img src={f.url} alt="" />
          ) : f.kind === "video" ? (
            <video src={f.url} muted playsInline />
          ) : (
            <span className="doc">{f.name.split(".").pop()?.toUpperCase()}</span>
          )}
          <span className="meta">
            <strong>{f.name}</strong>
            <small>{KIND_ICON[f.kind]}</small>
          </span>
          {onRemove && (
            <button type="button" aria-label={`${f.name} dosyasını kaldır`} onClick={() => onRemove(f.id)}>
              <Icon name="close" size={14} />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

export function UploadProgress({ busy }: { busy: { name: string; pct: number }[] }) {
  if (!busy.length) return null;
  return (
    <div className="upload-progress" aria-live="polite">
      {busy.map((b) => (
        <span key={b.name}>
          {b.name} yükleniyor… %{b.pct}
        </span>
      ))}
    </div>
  );
}
