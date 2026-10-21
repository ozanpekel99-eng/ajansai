"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { ApiError, api } from "../../lib/api";
import { HistoryEntry, readHistory } from "../../lib/history";
import { extractConcept, renderMarkdown } from "../../lib/markdown";
import { useSession } from "../../lib/session";
import { FileChips, PendingFile, UploadProgress, useUploader } from "../Attachments";
import Icon from "../Icon";
import { NoCreditsNotice, WorkspaceProps } from "./common";

type Msg = { role: "user" | "assistant"; content: string; attachments?: PendingFile[] };
type Conversation = { id: string; title: string; at: number; messages: Msg[] };

const CHATS_KEY = "ajansai_chats";
const MAX_FILES = 5;

const SUGGESTIONS = [
  "Beyaz eşya mağazam için bu hafta paylaşabileceğim 5 Reels fikri",
  "Kafem için yeni sezon soğuk kahve menüsünü tanıtan bir carousel yaz",
  "Eklediğim ürün fotoğrafına göre 3 farklı caption ve hashtag öner",
  "Emlak ofisim için Instagram reklam metni ve hedef kitle önerisi",
];

function loadChats(): Conversation[] {
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

export default function FikirWorkspace({ tab, showCreate }: WorkspaceProps) {
  const { usage, refresh } = useSession();
  const [chatId, setChatId] = useState<string>(() => `${Date.now()}`);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [chats, setChats] = useState<Conversation[]>([]);
  const [copied, setCopied] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);

  const uploader = useUploader(["image", "video", "document"], MAX_FILES, files.length, (f) => setFiles((x) => [...x, f]));

  useEffect(() => setChats(loadChats()), []);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [messages, sending]);

  const costs = usage?.costs;
  const cost = (costs?.chat_message ?? 1) + files.length * (costs?.chat_attachment ?? 1);
  const canSend = !sending && !uploader.busy.length && (text.trim().length > 0 || files.length > 0);

  const persist = (msgs: Msg[]) => {
    const title = (msgs.find((m) => m.role === "user")?.content || "Dosya incelemesi").slice(0, 70);
    const next = [{ id: chatId, title, at: Date.now(), messages: msgs }, ...loadChats().filter((c) => c.id !== chatId)];
    saveChats(next);
    setChats(next);
  };

  const send = async (e?: FormEvent, preset?: string) => {
    e?.preventDefault();
    const content = (preset ?? text).trim();
    if (!preset && !canSend) return;
    const userMsg: Msg = { role: "user", content, attachments: preset ? [] : files };
    const next = [...messages, userMsg];
    setMessages(next);
    setText("");
    setFiles([]);
    setError("");
    setSending(true);
    try {
      const data = await api<{ reply: string }>("/api/content/chat", {
        method: "POST",
        body: JSON.stringify({
          messages: next.map((m) => ({
            role: m.role,
            content: m.content,
            attachments: (m.attachments || []).map(({ url, content_type, name }) => ({ url, content_type, name })),
          })),
        }),
      });
      const done = [...next, { role: "assistant" as const, content: data.reply }];
      setMessages(done);
      persist(done);
    } catch (err) {
      setError((err as ApiError).message);
      // gönderilemeyen mesajı geri koy ki kullanıcı tekrar gönderebilsin
      setMessages(messages);
      setText(content);
      setFiles(userMsg.attachments || []);
    } finally {
      setSending(false);
      refresh();
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

  if (tab === "history") {
    const items: HistoryEntry<Conversation>[] = chats.map((c) => ({ id: c.id, title: c.title, at: c.at, data: c }));
    if (!items.length && readHistory("fikir").length === 0) {
      return (
        <div className="panel empty">
          <h3>Henüz sohbet yok</h3>
          <p>Oluştur sekmesinden ilk mesajını yaz; sohbetlerin burada listelenir. Geçmiş bu tarayıcıda saklanır.</p>
        </div>
      );
    }
    return (
      <div className="history">
        {items.map((item) => (
          <button
            key={item.id}
            className="history-item"
            style={{ textAlign: "left", cursor: "pointer", color: "inherit" }}
            onClick={() => {
              setChatId(item.data.id);
              setMessages(item.data.messages);
              showCreate();
            }}
          >
            <span>{item.title}</span>
            <span className="when">{new Date(item.at).toLocaleDateString("tr-TR")}</span>
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="chat">
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <h2>Bugün ne paylaşalım?</h2>
            <p>İşletmeni ve ne istediğini anlat. Ürün fotoğrafı, örnek video veya katalog eklersen onlara bakarak öneririm.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => send(undefined, s)} disabled={sending}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages">
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="msg user">
                  <FileChips files={m.attachments || []} />
                  {m.content && <div className="bubble">{m.content}</div>}
                </div>
              ) : (
                <div key={i} className="msg assistant">
                  <div className="avatar" aria-hidden="true">AI</div>
                  <div className="body">
                    <div className="md" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                    <div className="actions">
                      <button className="btn btn-ghost btn-sm" type="button" onClick={() => copy(m.content, i)}>
                        <Icon name="copy" size={14} /> {copied === i ? "Kopyalandı" : "Kopyala"}
                      </button>
                      <Link
                        className="btn btn-ghost btn-sm"
                        href={`/araclar/gorsel?konsept=${encodeURIComponent(extractConcept(m.content, "Görsel") || m.content.slice(0, 400))}`}
                      >
                        Görsel üret
                      </Link>
                      <Link
                        className="btn btn-ghost btn-sm"
                        href={`/araclar/video?konsept=${encodeURIComponent(extractConcept(m.content, "Video") || m.content.slice(0, 400))}`}
                      >
                        Video üret
                      </Link>
                    </div>
                  </div>
                </div>
              ),
            )}
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
        <NoCreditsNotice cost={cost} />
        {(error || uploader.error) && <div className="notice error">{error || uploader.error}</div>}
        <FileChips files={files} onRemove={(id) => setFiles((x) => x.filter((f) => f.id !== id))} />
        <UploadProgress busy={uploader.busy} />
        <div className="composer-box">
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
            placeholder="Ne paylaşmak istiyorsun? Ürün fotoğrafı, video ya da katalog da ekleyebilirsin…"
            aria-label="Mesaj"
          />
          <button type="submit" className="send-btn" disabled={!canSend} aria-label="Gönder">
            <Icon name="arrowUp" />
          </button>
        </div>
        <div className="composer-foot">
          <span>
            Bu mesaj {cost} kredi{files.length ? ` (mesaj 1 + ${files.length} dosya)` : ""} · Enter gönderir, Shift+Enter alt satır
          </span>
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
