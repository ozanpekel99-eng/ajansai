"use client";

import { FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { ApiError, api } from "../lib/api";
import { renderMarkdown } from "../lib/markdown";
import { FileChips, PendingFile, UploadProgress, useUploader } from "./Attachments";
import Icon from "./Icon";

export type Msg = {
  role: "user" | "assistant";
  content: string;
  attachments?: PendingFile[];
  images?: string[];
  imageError?: string | null;
};
export type Conversation = { id: string; title: string; at: number; messages: Msg[] };

/**
 * Ek ekleme biçimi:
 * - all: görsel, video, belge (ücretli paketler)
 * - images: yalnızca görsel (ücretsiz üye; görselden görsel üretimi için)
 * - signup: ataç düğmesi üye olmaya yönlendirir (ziyaretçi)
 */
export type AttachMode = "all" | "images" | "signup";

const CHATS_KEY = "ajansai_chats";

const SUGGESTIONS = [
  "Beyaz eşya mağazam için bu hafta paylaşabileceğim 5 Reels fikri",
  "Kafem için soğuk kahve kampanyasının gönderi görselini üret",
  "Emlak ofisim için Instagram reklam metni ve hedef kitle önerisi",
  "Kuaför salonum için bir haftalık hikâye planı hazırla",
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
  attach: AttachMode;
  /** Composer altındaki bilgi satırı (kredi veya ücretsiz hak). */
  footer: (files: number) => ReactNode;
  /** Gönderimi engelleyen durum (kredi/hak bitti) için uyarı; varsa gönderim kapalıdır. */
  blocker?: ReactNode;
  onSent?: (data: any) => void;
  /** Yanıttan video üretmeye geçiş bağlantısı (yoksa gösterilmez). */
  videoHref?: (text: string) => string | null;
  initial?: Conversation | null;
};

export default function ChatPanel({ endpoint, attach, footer, blocker, onSent, videoHref, initial }: Props) {
  const [chatId, setChatId] = useState<string>(() => initial?.id ?? `${Date.now()}`);
  const [messages, setMessages] = useState<Msg[]>(initial?.messages ?? []);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);

  const maxFiles = attach === "all" ? 5 : 2;
  const kinds = attach === "all" ? (["image", "video", "document"] as const) : (["image"] as const);
  const uploader = useUploader([...kinds], maxFiles, files.length, (f) => setFiles((x) => [...x, f]));

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  const canSend = !blocker && !sending && !uploader.busy.length && (text.trim().length > 0 || files.length > 0);

  const persist = (msgs: Msg[]) => {
    const title = (msgs.find((m) => m.role === "user")?.content || "Görsel").slice(0, 70);
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
      const data = await api<{ reply: string; images?: string[]; image_error?: string | null }>(endpoint, {
        method: "POST",
        body: JSON.stringify({
          messages: next.map((m) => ({
            role: m.role,
            content: m.content,
            attachments: (m.attachments || []).map(({ url, content_type, name }) => ({ url, content_type, name })),
          })),
        }),
      });
      const reply: Msg = { role: "assistant", content: data.reply, images: data.images || [], imageError: data.image_error };
      const done = [...next, reply];
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

  const lastUserWithImages = [...messages].reverse().find((m) => m.role === "user");
  const pendingImage = sending && /görsel|resim|fotoğraf|afiş|post|çiz/i.test(lastUserWithImages?.content || "");

  return (
    <div className="chat">
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <h2>Hadi sohbete başlayalım</h2>
            <p>İşletmeni ve ne istediğini anlat. Paylaşım fikri, caption, reklam metni ya da görsel; ne istersen yaz.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
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
              const vid = videoHref?.(m.content);
              return (
                <div key={i} className="msg assistant">
                  <div className="avatar" aria-hidden="true">AI</div>
                  <div className="body">
                    {m.content && <div className="md" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />}
                    {!!m.images?.length && (
                      <div className="msg-images">
                        {m.images.map((url) => (
                          <figure key={url}>
                            <img src={url} alt="Üretilen görsel" />
                            <a className="btn btn-light btn-sm" href={url} target="_blank" rel="noreferrer" download>
                              İndir
                            </a>
                          </figure>
                        ))}
                      </div>
                    )}
                    {m.imageError && <div className="notice">{m.imageError}</div>}
                    <div className="actions">
                      <button className="btn btn-ghost btn-sm" type="button" onClick={() => copy(m.content, i)}>
                        <Icon name="copy" size={14} /> {copied === i ? "Kopyalandı" : "Kopyala"}
                      </button>
                      {!m.images?.length && i === messages.length - 1 && (
                        <button
                          className="btn btn-ghost btn-sm"
                          type="button"
                          disabled={sending || !!blocker}
                          onClick={() => send(undefined, "Bunun için bir gönderi görseli üret")}
                        >
                          <Icon name="image" size={14} /> Görselini üret
                        </button>
                      )}
                      {vid && (
                        <Link className="btn btn-ghost btn-sm" href={vid}>
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
                <div className="body">
                  <div className="typing">
                    <span />
                    <span />
                    <span />
                  </div>
                  {pendingImage && <div className="faint" style={{ fontSize: 13, marginTop: 6 }}>Görsel istendiyse birlikte hazırlanıyor, 10–20 saniye sürebilir.</div>}
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
          {attach === "signup" ? (
            <Link href="/kayit" className="icon-btn" aria-label="Görsel eklemek için üye ol" title="Görsel eklemek için üye ol">
              <Icon name="clip" />
            </Link>
          ) : (
            <>
              {uploader.field}
              <button
                type="button"
                className="icon-btn"
                onClick={uploader.pick}
                disabled={files.length >= maxFiles}
                aria-label={attach === "all" ? "Görsel, video veya belge ekle" : "Görsel ekle"}
                title={attach === "all" ? "Görsel, video veya belge ekle" : "Görsel ekle (görselden görsel üretebilirsin)"}
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
            placeholder="Bir şey sor ya da bir görsel iste…"
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
