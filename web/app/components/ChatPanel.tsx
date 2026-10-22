"use client";

import { downloadHref } from "../lib/download";
import { FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { ApiError, api } from "../lib/api";
import { renderMarkdown } from "../lib/markdown";
import { useVoice } from "../lib/voice";
import { FileChips, PendingFile, UploadProgress, useUploader } from "./Attachments";
import Icon from "./Icon";

export type Msg = {
  role: "user" | "assistant";
  content: string;
  attachments?: PendingFile[];
  images?: string[];
  imageError?: string | null;
  sources?: { title: string; url: string }[];
  files?: { name: string; url: string; format: string; size: number; title: string }[];
  videos?: ChatVideo[];
};
export type ChatVideo = { job_id: string; aspect: string; url?: string | null; error?: string | null };
type Mode = "chat" | "image" | "search" | "file" | "video";
export type Conversation = { id: string; title: string; at: number; messages: Msg[] };

/**
 * Ek ekleme biçimi:
 * - all: görsel, video, belge (ücretli paketler)
 * - basic: görsel ve belge (ücretsiz paket ve ziyaretçi)
 */
export type AttachMode = "all" | "basic";

/** + menüsündeki ek araçlar: href yoksa kilitli (locked açıklamasıyla). */
export type MenuTool = { href: string; locked?: string };

const CHATS_KEY = "ajansai_chats";

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
  /** + menüsünde gösterilecek video / reklam araçları */
  tools?: { video?: MenuTool; ads?: MenuTool };
  /** Video sohbetin içinde üretilir (+ menüsünde "Video oluştur" modu). */
  videoInChat?: boolean;
  initial?: Conversation | null;
};

export default function ChatPanel({ endpoint, attach, footer, blocker, onSent, videoHref, tools, videoInChat, initial }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("chat");
  const imageMode = mode === "image";
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenuOpen(false);
    const esc = (e: globalThis.KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [menuOpen]);

  const [chatId, setChatId] = useState<string>(() => initial?.id ?? `${Date.now()}`);
  const [messages, setMessages] = useState<Msg[]>(initial?.messages ?? []);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);

  // Sesli sohbet
  const voice = useVoice();
  const [voiceMode, setVoiceMode] = useState(false);
  const [interim, setInterim] = useState("");
  const [speakingIdx, setSpeakingIdx] = useState<number | null>(null);
  const voiceModeRef = useRef(false);
  const messagesRef = useRef<Msg[]>(messages);
  messagesRef.current = messages;

  const maxFiles = attach === "all" ? 5 : 3;
  const kinds = attach === "all" ? (["image", "video", "document"] as const) : (["image", "document"] as const);
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
    const messages = messagesRef.current;
    const userMsg: Msg = { role: "user", content, attachments: preset ? [] : files };
    const next = [...messages, userMsg];
    setMessages(next);
    setText("");
    setFiles([]);
    setError("");
    setSending(true);
    try {
      const data = await api<{ reply: string; images?: string[]; image_error?: string | null; sources?: { title: string; url: string }[]; files?: Msg["files"]; videos?: ChatVideo[] }>(endpoint, {
        method: "POST",
        body: JSON.stringify({
          mode,
          messages: next.map((m) => ({
            role: m.role,
            content: m.role === "assistant" ? m.content + historyNote(m) : m.content,
            ...(m.role === "assistant" && m.images?.length ? { media: m.images.filter((u) => u.startsWith("http")).slice(0, 4) } : {}),
            attachments: (m.attachments || []).map(({ url, content_type, name }) => ({ url, content_type, name })),
          })),
        }),
      });
      const reply: Msg = {
        role: "assistant",
        content: data.reply,
        images: data.images || [],
        imageError: data.image_error,
        sources: data.sources || [],
        files: data.files || [],
        videos: data.videos || [],
      };
      setMode("chat");
      const done = [...next, reply];
      setMessages(done);
      messagesRef.current = done;
      persist(done);
      onSent?.(data);
      if (voiceModeRef.current) {
        setSpeakingIdx(done.length - 1);
        voice.speak(reply.content, () => {
          setSpeakingIdx(null);
          if (voiceModeRef.current) voiceTurn();
        });
      }
    } catch (err) {
      setError((err as ApiError).message);
      // gönderilemeyen mesajı geri koy ki kullanıcı tekrar gönderebilsin
      setMessages(messages);
      setText(content);
      setFiles(userMsg.attachments || []);
      onSent?.(null);
      if (voiceModeRef.current) stopVoiceMode();
    } finally {
      setSending(false);
    }
  };

  // Sesli sohbet: dinle → gönder → yanıtı sesli oku → tekrar dinle
  function voiceTurn() {
    voice.listen({
      onInterim: setInterim,
      onFinal: (t) => {
        setInterim("");
        if (!voiceModeRef.current) return;
        if (t) send(undefined, t);
        else stopVoiceMode(); // sessizlikte mod kapanır
      },
      onError: (msg) => {
        setError(msg);
        stopVoiceMode();
      },
    });
  }

  function startVoiceMode() {
    voice.stopSpeaking();
    voice.unlock();
    setError("");
    voiceModeRef.current = true;
    setVoiceMode(true);
    voiceTurn();
  }

  function stopVoiceMode() {
    voiceModeRef.current = false;
    setVoiceMode(false);
    setInterim("");
    voice.cancelListening();
    voice.stopSpeaking();
    setSpeakingIdx(null);
  }

  // Konuşarak yazdırma (mikrofon düğmesi)
  const dictate = () => {
    if (voice.listening) return voice.stopListening();
    const base = text ? `${text.trimEnd()} ` : "";
    voice.listen({
      onInterim: (t) => setText(base + t),
      onFinal: (t) => {
        setText((base + t).trimEnd());
        boxRef.current?.focus();
      },
      onError: setError,
    });
  };

  const readAloud = (i: number, content: string) => {
    if (speakingIdx === i) {
      voice.stopSpeaking();
      setSpeakingIdx(null);
      return;
    }
    setSpeakingIdx(i);
    voice.unlock();
    voice.speak(content, () => setSpeakingIdx(null));
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

  const updateVideo = (idx: number, v: ChatVideo) => {
    const list = messagesRef.current.map((m, k) =>
      k === idx ? { ...m, videos: (m.videos || []).map((x) => (x.job_id === v.job_id ? v : x)) } : m,
    );
    messagesRef.current = list;
    setMessages(list);
    persist(list);
    if (v.url) onSent?.(null);
  };

  const lastUserWithImages = [...messages].reverse().find((m) => m.role === "user");
  const pendingSearch = sending && mode === "search";
  const pendingFile = sending && (mode === "file" || /sunum|slayt|pdf|word|excel|rapor|belge|tablo/i.test(lastUserWithImages?.content || ""));
  const pendingVideo = sending && (mode === "video" || (!!videoInChat && /video|reels|animasyon/i.test(lastUserWithImages?.content || "")));
  const pendingImage = sending && !pendingVideo && (imageMode || /görsel|resim|fotoğraf|afiş|post|çiz/i.test(lastUserWithImages?.content || ""));

  return (
    <div className={`chat ${messages.length === 0 ? "is-empty" : ""}`}>
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <h2>Nasıl yardımcı olabilirim?</h2>
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
                            <a className="btn btn-light btn-sm" href={downloadHref(url)} download>
                              İndir
                            </a>
                          </figure>
                        ))}
                      </div>
                    )}
                    {!!m.files?.length && (
                      <div className="msg-files">
                        {m.files.map((f) => (
                          <a key={f.url} className="file-card" href={downloadHref(f.url)} download={f.name}>
                            <span className={`file-badge ${f.format}`}>{f.format.toUpperCase()}</span>
                            <span className="file-meta">
                              <strong>{f.title}</strong>
                              <small>
                                {f.name} · {f.size > 1024 * 1024 ? `${(f.size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(f.size / 1024))} KB`}
                              </small>
                            </span>
                            <span className="btn btn-light btn-sm">İndir</span>
                          </a>
                        ))}
                      </div>
                    )}
                    {!!m.videos?.length && (
                      <div className="msg-images">
                        {m.videos.map((v) => (
                          <VideoCard key={v.job_id} video={v} onUpdate={(nv) => updateVideo(i, nv)} />
                        ))}
                      </div>
                    )}
                    {m.imageError && <div className="notice">{m.imageError}</div>}
                    {!!m.sources?.length && (
                      <div className="sources">
                        <span className="faint">Kaynaklar</span>
                        {m.sources.map((src, k) => (
                          <a key={src.url} href={src.url} target="_blank" rel="noreferrer" title={src.title}>
                            <span className="n">{k + 1}</span>
                            {hostOf(src.url)}
                          </a>
                        ))}
                      </div>
                    )}
                    <div className="actions">
                      <button className="btn btn-ghost btn-sm" type="button" onClick={() => copy(m.content, i)}>
                        <Icon name="copy" size={14} /> {copied === i ? "Kopyalandı" : "Kopyala"}
                      </button>
                      {voice.canSpeak && m.content && (
                        <button className="btn btn-ghost btn-sm" type="button" onClick={() => readAloud(i, m.content)}>
                          <Icon name={speakingIdx === i ? "stop" : "speaker"} size={14} /> {speakingIdx === i ? "Durdur" : "Sesli oku"}
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
                  {pendingImage && <div className="faint" style={{ fontSize: 13, marginTop: 6 }}>Görsel hazırlanıyor…</div>}
                  {pendingVideo && <div className="faint" style={{ fontSize: 13, marginTop: 6 }}>Video başlatılıyor…</div>}
                  {pendingSearch && <div className="faint" style={{ fontSize: 13, marginTop: 6 }}>İnternette aranıyor…</div>}
                  {pendingFile && !pendingImage && !pendingSearch && (
                    <div className="faint" style={{ fontSize: 13, marginTop: 6 }}>Dosya istendiyse hazırlanıyor, 20–40 saniye sürebilir…</div>
                  )}
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
        {voiceMode && (
          <div className="voice-bar" role="status">
            <span className={`voice-dot ${voice.listening ? "on" : ""}`} aria-hidden="true" />
            <span className="voice-state">
              {voice.listening ? interim || "Dinliyorum…" : sending ? "Düşünüyor…" : voice.speaking ? "Konuşuyor…" : "Hazır"}
            </span>
            <button type="button" className="btn btn-light btn-sm" onClick={stopVoiceMode}>
              Bitir
            </button>
          </div>
        )}
        {mode !== "chat" && (
          <div className="mode-chip">
            <Icon name={mode === "image" ? "image" : mode === "file" ? "file" : mode === "video" ? "video" : "globe"} size={14} />{" "}
            {mode === "image" ? "Görsel oluştur" : mode === "file" ? "Dosya oluştur" : mode === "video" ? "Video oluştur" : "Web'de ara"}
            <button type="button" aria-label="Modu kapat" onClick={() => setMode("chat")}>
              <Icon name="close" size={12} />
            </button>
          </div>
        )}
        <div className="composer-box">
          {uploader.field}
          <div className="plus-wrap" ref={menuRef}>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setMenuOpen((o) => !o)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Ekle ve araçlar"
            >
              <Icon name="plus" />
            </button>
            {menuOpen && (
              <div className="plus-menu" role="menu">
                <button
                  type="button"
                  role="menuitem"
                  disabled={files.length >= maxFiles}
                  onClick={() => {
                    setMenuOpen(false);
                    uploader.pick();
                  }}
                >
                  <Icon name="clip" size={18} />
                  <span>
                    <strong>Fotoğraf ve dosya ekle</strong>
                    <small>{attach === "all" ? "Görsel, video, PDF, Word, metin" : "Görsel, PDF, Word, metin"}</small>
                  </span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    setMode("image");
                    boxRef.current?.focus();
                  }}
                >
                  <Icon name="image" size={18} />
                  <span>
                    <strong>Görsel oluştur</strong>
                    <small>Tarif et ya da eklediğin görselden üret</small>
                  </span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    setMode("file");
                    boxRef.current?.focus();
                  }}
                >
                  <Icon name="file" size={18} />
                  <span>
                    <strong>Dosya oluştur</strong>
                    <small>Görselli sunum, PDF, Word veya Excel</small>
                  </span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    setMode("search");
                    boxRef.current?.focus();
                  }}
                >
                  <Icon name="globe" size={18} />
                  <span>
                    <strong>Web'de ara</strong>
                    <small>Güncel haber ve bilgileri bul</small>
                  </span>
                </button>
                {videoInChat ? (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      setMode("video");
                      boxRef.current?.focus();
                    }}
                  >
                    <Icon name="video" size={18} />
                    <span>
                      <strong>Video oluştur</strong>
                      <small>Tarif et ya da eklediğin görselden canlandır</small>
                    </span>
                  </button>
                ) : (
                  tools?.video && <MenuLink icon="video" title="Video oluştur" desc="Reels ve hikâye için kısa video" tool={tools.video} />
                )}
                {tools?.ads && <MenuLink icon="megaphone" title="Reklam oluştur" desc="Instagram reklamını kur ve yayınla" tool={tools.ads} />}
              </div>
            )}
          </div>
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
              mode === "image"
                ? "Görseli tarif et…"
                : mode === "video"
                  ? "Videoyu tarif et… Örn. buzlu kahve bardağa dökülüyor, ağır çekim"
                : mode === "search"
                  ? "Ne aramak istiyorsun?"
                  : mode === "file"
                    ? "Ne hazırlayayım? Örn. kafem için 8 slaytlık görselli sunum (PDF)"
                    : "Bir şey sor…"
            }
            aria-label="Mesaj"
          />
          {voice.canListen && (
            <button
              type="button"
              className={`icon-btn ${voice.listening && !voiceMode ? "rec" : ""}`}
              onClick={dictate}
              disabled={voiceMode}
              aria-label={voice.listening && !voiceMode ? "Dinlemeyi bitir" : "Konuşarak yaz"}
              title="Konuşarak yaz"
            >
              <Icon name="mic" />
            </button>
          )}
          {voice.canListen && voice.canSpeak && !text.trim() && !files.length ? (
            <button
              type="button"
              className={`send-btn ${voiceMode ? "active" : ""}`}
              onClick={voiceMode ? stopVoiceMode : startVoiceMode}
              disabled={!!blocker}
              aria-label={voiceMode ? "Sesli sohbeti bitir" : "Sesli sohbet"}
              title="Sesli sohbet"
            >
              <Icon name={voiceMode ? "stop" : "wave"} />
            </button>
          ) : (
          <button type="submit" className="send-btn" disabled={!canSend} aria-label="Gönder">
            <Icon name="arrowUp" />
          </button>
          )}
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

function MenuLink({ icon, title, desc, tool }: { icon: string; title: string; desc: string; tool: MenuTool }) {
  return (
    <Link href={tool.href} role="menuitem" className={tool.locked ? "locked" : ""}>
      <Icon name={icon} size={18} />
      <span>
        <strong>{title}</strong>
        <small>{tool.locked || desc}</small>
      </span>
    </Link>
  );
}

function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Sohbette başlatılan video: hazır olana kadar 5 sn'de bir durumu sorar. */
function VideoCard({ video, onUpdate }: { video: ChatVideo; onUpdate: (v: ChatVideo) => void }) {
  const [elapsed, setElapsed] = useState(0);
  const done = !!video.url || !!video.error;
  const updateRef = useRef(onUpdate);
  updateRef.current = onUpdate;

  useEffect(() => {
    if (done) return;
    let stop = false;
    const started = Date.now();
    const tick = async () => {
      if (stop) return;
      setElapsed(Math.round((Date.now() - started) / 1000));
      try {
        const r = await api<{ status: string; video_url: string | null; error: string | null }>(`/api/content/video/${video.job_id}`);
        if (stop) return;
        if (r.status === "SUCCEEDED" && r.video_url) return updateRef.current({ ...video, url: r.video_url });
        if (r.status === "FAILED") return updateRef.current({ ...video, error: r.error || "Video üretilemedi, kredin iade edildi." });
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return updateRef.current({ ...video, error: "Video bulunamadı." });
      }
      timer = window.setTimeout(tick, 5000);
    };
    let timer = window.setTimeout(tick, 4000);
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [video.job_id, done]); // eslint-disable-line react-hooks/exhaustive-deps

  const ratio = video.aspect === "16:9" ? "16 / 9" : video.aspect === "1:1" ? "1 / 1" : "9 / 16";
  if (video.error) return <div className="notice">{video.error}</div>;
  if (!video.url) {
    return (
      <figure className="video-pending" style={{ aspectRatio: ratio }}>
        <div className="typing">
          <span />
          <span />
          <span />
        </div>
        <small>Video hazırlanıyor{elapsed ? ` · ${elapsed} sn` : ""}</small>
        <small className="faint">Genelde 1–3 dakika sürer, bu sayfadan ayrılabilirsin.</small>
      </figure>
    );
  }
  return (
    <figure>
      <video src={video.url} controls playsInline style={{ aspectRatio: ratio }} />
      <a className="btn btn-light btn-sm" href={downloadHref(video.url)} download>
        İndir
      </a>
    </figure>
  );
}

/** Önceki yanıtta sistemin yaptığı işler (görsel, arama, dosya, video) modele not olarak iletilir. */
function historyNote(m: Msg): string {
  const notes: string[] = [];
  if (m.sources?.length) notes.push(`bu yanıt web aramasıyla yazıldı (kaynaklar: ${m.sources.map((s) => hostOf(s.url)).join(", ")})`);
  if (m.files?.length) notes.push(`dosya oluşturulup kullanıcıya verildi: ${m.files.map((f) => f.name).join(", ")}`);
  if (m.videos?.length) notes.push(m.videos.some((v) => v.url) ? "video üretilip kullanıcıya gösterildi" : "video üretimi başlatıldı");
  return notes.length ? `\n\n[Sistem notu: ${notes.join("; ")}.]` : "";
}
