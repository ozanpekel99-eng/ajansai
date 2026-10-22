"use client";

import { FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { ApiError, api } from "../lib/api";
import { extractConcept, renderMarkdown } from "../lib/markdown";
import { FileChips, PendingFile, UploadProgress, useUploader } from "./Attachments";
import Icon from "./Icon";

export type Msg = { role: "user" | "assistant"; content: string; attachments?: PendingFile[] };
export type Conversation = { id: string; title: string; at: number; messages: Msg[] };

const CHATS_KEY = "ajansai_chats";
const MAX_FILES = 5;

const SUGGESTIONS = [
  "Beyaz eşya mağazam için bu hafta paylaşabileceğim 5 Reels fikri",
  "Kafem için yeni sezon soğuk kahve menüsünü tanıtan bir carousel yaz",
  "Eklediğim ürün fotoğrafına göre 3 farklı caption ve hashtag öner",
  "Emlak ofisim için Instagram reklam metni ve hedef kitle önerisi",
];

export function loadChats(): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(CHATS_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveChats(list: Conversation[]) {
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(list.slice(0, 30)));
  } catch {
    // depolama kapalıysa sohbet yalnızca bu sekmede kalır
  }
}

type Props = {
  endpoint: string;
  allowFiles: boolean;
  /** Composer altındaki bilgi satırı (kredi veya ücretsiz hak). */
  footer: (files: number) => ReactNode;
  /** Gönderimi engelleyen durum (kredi/hak bitti) için uyarı; varsa gönderim kapalıdır. */
  blocker?: ReactNode;
  onSent?: (data: any) => void;
  conceptHref: (kind: "gorsel" | "video", concept: string) => string | null;
  initial?: Conversation | null;
  placeholder?: string;
};

export default function ChatPanel({ endpoint, allowFiles, footer, blocker, onSent, conceptHref, initial, placeholder }: Props) {
  const [chatId, setChatId] = useState<string>(() => initial?.id ?? `${Date.now()}`);
  const [messages, setMessages] = useState<Msg[]>(initial?.messages ?? []);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);

  const uploader = useUploader(["image", "video", "document"], MAX_FILES, files.length, (f) => setFiles((x) => [...x, f]));

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  const canSend = !blocker && !sending && !uploader.busy.length && (text.trim().length > 0 || files.length > 0);

  const persist = (msgs: Msg[]) => {
    const title = (msgs.find((m) => m.role === "user")?.content || "Dosya incelemesi").slice(0, 70);
    saveChats([{ id: chatId, title, at: Date.now(), messages: msgs }, ...loadChats().filter((c) => c.id !== chatId)]);
  };

  const send = async (e?: FormEvent, preset?: string) => {
    e?.preventDefault();
    const content = (preset ?? text).trim();
    if (blocker || sending || (!preset && !canSend)) return;
    const userMsg: Msg = { role: "user", content, attachments: preset ? [] : files };
    const next = [...messages, userMsg];
    setMessages(next);
    setText("");
    setFiles([]);
    setError("");
    setSending(true);
    try {
      const data = await api<{ reply: string }>(endpoint, {
        method: "POST",
        body: JSON.stringify({
          messages: next.map((m) =>
            allowFiles
              ? {
                  role: m.role,
                  content: m.content,
                  attachments: (m.attachments || []).map(({ url, content_type, name }) => ({ url, content_type, name })),
                }
              : { role: m.role, content: m.content },
          ),
        }),
      });
      const done = [...next, { role: "assistant" as const, content: data.reply }];
      setMessages(done);
      persist(done);
      onSent?.(data);
    } catch (err) {
      setError((err as ApiError).message);
      // gönderilemeyen mesajı geri koy ki kullanıcı tekrar gönderebilsin
      setMessages(messages);
      setText(content);
      setFiles(userMsg.attachments || []);
      onSent?.(null);
    } finally {
      setSending(false);
    }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const newChat = () => {
    setChatId(`${Date.now()}`);
    setMessages([]);
    setError("");
    boxRef.current?.focus();
  };

  const copy = async (content: string, i: number) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(i);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // pano izni yoksa sessizce geç
    }
  };

  const suggestions = allowFiles ? SUGGESTIONS : SUGGESTIONS.filter((s) => !s.startsWith("Eklediğim"));

  return (
    <div className="chat">
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <h2>Bugün ne paylaşalım?</h2>
            <p>
              {allowFiles
                ? "İşletmeni ve ne istediğini anlat. Ürün fotoğrafı, örnek video veya katalog eklersen onlara bakarak öneririm."
                : "İşletmeni ve ne istediğini anlat; fikir, caption, hashtag ve reklam metni yazayım."}
            </p>
            <div className="suggestions">
              {suggestions.map((s) => (
                <button key={s} type="button" onClick={() => send(undefined, s)} disabled={sending || !!blocker}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages">
            {messages.map((m, i) => {
              if (m.role === "user") {
                return (
                  <div key={i} className="msg user">
                    <FileChips files={m.attachments || []} />
                    {m.content && <div className="bubble">{m.content}</div>}
                  </div>
                );
              }
              const imgHref = conceptHref("gorsel", extractConcept(m.content, "Görsel") || m.content.slice(0, 400));
              const vidHref = conceptHref("video", extractConcept(m.content, "Video") || m.content.slice(0, 400));
              return (
                <div key={i} className="msg assistant">
                  <div className="avatar" aria-hidden="true">AI</div>
                  <div className="body">
                    <div className="md" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                    <div className="actions">
                      <button className="btn btn-ghost btn-sm" type="button" onClick={() => copy(m.content, i)}>
                        <Icon name="copy" size={14} /> {copied === i ? "Kopyalandı" : "Kopyala"}
                      </button>
                      {imgHref && (
                        <Link className="btn btn-ghost btn-sm" href={imgHref}>
                          Görsel üret
                        </Link>
                      )}
                      {vidHref && (
                        <Link className="btn btn-ghost btn-sm" href={vidHref}>
                          Video üret
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {sending && (
              <div className="msg assistant">
                <div className="avatar" aria-hidden="true">AI</div>
                <div className="body typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={send}>
        {blocker}
        {(error || uploader.error) && <div className="notice error">{error || uploader.error}</div>}
        <FileChips files={files} onRemove={(id) => setFiles((x) => x.filter((f) => f.id !== id))} />
        <UploadProgress busy={uploader.busy} />
        <div className="composer-box">
          {allowFiles && (
            <>
              {uploader.field}
              <button
                type="button"
                className="icon-btn"
                onClick={uploader.pick}
                disabled={files.length >= MAX_FILES}
                aria-label="Görsel, video veya belge ekle"
                title="Görsel, video veya belge ekle"
              >
                <Icon name="clip" />
              </button>
            </>
          )}
          <textarea
            ref={boxRef}
            rows={1}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 220)}px`;
            }}
            onKeyDown={onKey}
            placeholder={
              placeholder ??
              (allowFiles
                ? "Ne paylaşmak istiyorsun? Ürün fotoğrafı, video ya da katalog da ekleyebilirsin…"
                : "Ne paylaşmak istiyorsun? İşletmeni ve fikrini yaz…")
            }
            aria-label="Mesaj"
          />
          <button type="submit" className="send-btn" disabled={!canSend} aria-label="Gönder">
            <Icon name="arrowUp" />
          </button>
        </div>
        <div className="composer-foot">
          <span>{footer(files.length)}</span>
          {messages.length > 0 && (
            <button type="button" className="link-btn" onClick={newChat}>
              <Icon name="plus" size={14} /> Yeni sohbet
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
