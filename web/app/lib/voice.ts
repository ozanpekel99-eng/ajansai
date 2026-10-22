"use client";

// Sesli sohbet: tarayıcının kendi konuşma tanıma (SpeechRecognition) ve sesli
// okuma (speechSynthesis) özellikleri. Ek sunucu maliyeti yoktur.

import { useCallback, useEffect, useRef, useState } from "react";

import { API_URL, getToken } from "./api";

// Kısa sessiz MP3: iOS'ta ses çalabilmek için kullanıcı dokunuşunda bir kez çalınır.
const SILENT =
  "data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYwLjE2LjEwMAAAAAAAAAAAAAAA//NwwAAAAAAAAAAAAEluZm8AAAAPAAAABgAAAykAWlpaWlpaWlpaWlpaWlpaWnt7e3t7e3t7e3t7e3t7e3t7nJycnJycnJycnJycnJycnL29vb29vb29vb29vb29vb293t7e3t7e3t7e3t7e3t7e3t7/////////////////////AAAAAExhdmM2MC4zMQAAAAAAAAAAAAAAACQCowAAAAAAAAMpso+sIAAAAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NCxKMAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NAxKQAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/80LEowAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVU=";

/** Metni parçalara böler: ilk parça çok kısa (ses hemen başlasın), sonrakiler giderek uzar.
 * Parçalar paralel üretildiği için bir parça çalarken sonrakiler hazır olur. */
const LIMITS = [70, 160, 360, 600];
function chunks(text: string): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const out: string[] = [];
  let cur = "";
  for (const w of words) {
    const limit = LIMITS[Math.min(out.length, LIMITS.length - 1)];
    const next = cur ? `${cur} ${w}` : w;
    // Sınıra yaklaşınca cümle sonunda ya da sınırı aşınca kelime sınırında böl
    if (cur && (next.length > limit || (cur.length > limit * 0.6 && /[.!?…:;]$/.test(cur)))) {
      out.push(cur);
      cur = w;
    } else {
      cur = next;
    }
  }
  if (cur) out.push(cur);
  return out;
}

/** Tek parçayı PCM (24 kHz, 16-bit) olarak alır; olmazsa null. */
async function fetchPcm(text: string): Promise<Uint8Array | null> {
  try {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/voice/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return null;
    const buf = new Uint8Array(await res.arrayBuffer());
    return buf.length >= 2 ? buf : null;
  } catch {
    return null;
  }
}

async function fetchSpeech(text: string): Promise<string | null> {
  try {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  } catch {
    return null;
  }
}

const RATE = 24000;

/** Akışlı ses: gelen PCM parçalarını kesintisiz sırayla çalar. */
export class PcmPlayer {
  ctx: AudioContext;
  next = 0;
  sources: AudioBufferSourceNode[] = [];
  constructor(ctx: AudioContext) {
    this.ctx = ctx;
  }
  push(bytes: Uint8Array) {
    const n = Math.floor(bytes.length / 2);
    if (!n) return;
    const view = new DataView(bytes.buffer, bytes.byteOffset, n * 2);
    const buf = this.ctx.createBuffer(1, n, RATE);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < n; i++) ch[i] = view.getInt16(i * 2, true) / 32768;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.ctx.destination);
    const at = Math.max(this.ctx.currentTime + 0.03, this.next);
    src.start(at);
    this.next = at + buf.duration;
    this.sources.push(src);
  }
  /** Kalan çalma süresi (ms) */
  remaining() {
    return Math.max(0, (this.next - this.ctx.currentTime) * 1000);
  }
  stop() {
    for (const s of this.sources) {
      try {
        s.stop();
      } catch {
        // zaten bitmiş
      }
    }
    this.sources = [];
    this.next = 0;
  }
}

type Recognition = any;

function recognitionCtor(): (new () => Recognition) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

/** Sesli okumaya uygun düz metin: markdown işaretleri ve uzun bağlantılar çıkarılır. */
export function speakableText(md: string) {
  return md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[#*_`>|]/g, " ")
    .replace(/^\s*[-•]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

function turkishVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis?.getVoices() || [];
  return (
    voices.find((v) => v.lang === "tr-TR" && /natural|online|neural|google/i.test(v.name)) ||
    voices.find((v) => v.lang?.toLowerCase().startsWith("tr")) ||
    null
  );
}

export function useVoice() {
  const [canListen, setCanListen] = useState(false);
  const [canSpeak, setCanSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const recRef = useRef<Recognition | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const playerRef = useRef<PcmPlayer | null>(null);
  const streamOk = useRef(true);
  const speakId = useRef(0);

  useEffect(() => {
    setCanListen(!!recognitionCtor());
    setCanSpeak(typeof window !== "undefined" && ("speechSynthesis" in window || "Audio" in window));
    // Bazı tarayıcılar sesleri geç yükler
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.getVoices();
    return () => {
      recRef.current?.abort?.();
      if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    };
  }, []);

  /** Bir kez dinler: ara sonuçları onInterim'e, cümle bitince sonucu onFinal'e verir. */
  const listen = useCallback(
    (opts: { onInterim?: (t: string) => void; onFinal: (t: string) => void; onError?: (msg: string) => void }) => {
      const Ctor = recognitionCtor();
      if (!Ctor) return;
      recRef.current?.abort?.();
      const rec = new Ctor();
      rec.lang = "tr-TR";
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      let finalText = "";
      rec.onresult = (e: any) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          if (r.isFinal) finalText += r[0].transcript;
          else interim += r[0].transcript;
        }
        opts.onInterim?.((finalText + interim).trim());
      };
      rec.onerror = (e: any) => {
        if (e.error === "not-allowed" || e.error === "service-not-allowed") opts.onError?.("Mikrofon izni verilmedi. Tarayıcı ayarlarından izin verebilirsin.");
        else if (e.error !== "no-speech" && e.error !== "aborted") opts.onError?.("Ses anlaşılamadı, tekrar dene.");
      };
      rec.onend = () => {
        setListening(false);
        recRef.current = null;
        opts.onFinal(finalText.trim());
      };
      recRef.current = rec;
      setListening(true);
      try {
        rec.start();
      } catch {
        setListening(false);
      }
    },
    [],
  );

  const stopListening = useCallback(() => {
    recRef.current?.stop?.();
  }, []);

  const cancelListening = useCallback(() => {
    if (recRef.current) {
      recRef.current.onend = () => {
        setListening(false);
        recRef.current = null;
      };
      recRef.current.abort?.();
    }
  }, []);

  /** Kullanıcı dokunuşunda çağrılır: mobil tarayıcılarda sonraki sesli okumaya izin açar. */
  const unlock = useCallback(() => {
    if (!audioRef.current) audioRef.current = new Audio();
    const a = audioRef.current;
    a.src = SILENT;
    a.play().catch(() => {});
    audioCtx();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /** Akışlı ses için AudioContext (kullanıcı dokunuşunda açılır). */
  const audioCtx = (): AudioContext | null => {
    if (typeof window === "undefined") return null;
    const AC = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AC) return null;
    if (!ctxRef.current) ctxRef.current = new AC();
    if (ctxRef.current!.state === "suspended") ctxRef.current!.resume().catch(() => {});
    return ctxRef.current;
  };

  /** Tarayıcının kendi sesi (doğal ses kullanılamazsa). */
  const browserSpeak = useCallback((text: string, onEnd?: () => void) => {
    if (!("speechSynthesis" in window)) return onEnd?.();
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "tr-TR";
    const v = turkishVoice();
    if (v) u.voice = v;
    u.rate = 1.05;
    u.onend = () => {
      setSpeaking(false);
      onEnd?.();
    };
    u.onerror = () => {
      setSpeaking(false);
    };
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  }, []);

  /** Önce doğal ses (Google Chirp 3 HD), olmazsa tarayıcının sesi. Parça parça çalar. */
  const speak = useCallback(
    (md: string, onEnd?: () => void) => {
      const text = speakableText(md).slice(0, 4000);
      const id = ++speakId.current;
      playerRef.current?.stop();
      window.speechSynthesis?.cancel();
      if (!text) return onEnd?.();
      if (!audioRef.current) audioRef.current = new Audio();
      const audio = audioRef.current;
      const list = chunks(text);
      setSpeaking(true);

      (async () => {
        // 1) Doğal ses (PCM): parçalar 3'erli paralel üretilir, sırayla kesintisiz çalınır
        const ctx = streamOk.current ? audioCtx() : null;
        if (ctx) {
          const player = new PcmPlayer(ctx);
          playerRef.current = player;
          const alive = () => speakId.current === id;
          const jobs: Promise<Uint8Array | null>[] = [];
          const ensure = (k: number) => {
            for (let j = jobs.length; j < Math.min(list.length, k + 3); j++) jobs.push(fetchPcm(list[j]));
          };
          for (let i = 0; i < list.length; i++) {
            ensure(i);
            const pcm = await jobs[i];
            if (!alive()) return;
            if (!pcm) {
              if (i === 0) {
                streamOk.current = false; // bu oturumda doğal ses yok: dosya yoluna geç
                break;
              }
              // Hak bitti ya da hata: kalan metni tarayıcı sesiyle, mevcut ses bitince
              await new Promise((r) => setTimeout(r, player.remaining()));
              if (!alive()) return;
              return browserSpeak(list.slice(i).join(" "), onEnd);
            }
            player.push(pcm);
          }
          if (streamOk.current) {
            await new Promise((r) => setTimeout(r, player.remaining() + 50));
            if (!alive()) return;
            setSpeaking(false);
            onEnd?.();
            return;
          }
        }
        // 2) Dosya olarak doğal ses, 3) tarayıcı sesi
        let next: Promise<string | null> = fetchSpeech(list[0]);
        for (let i = 0; i < list.length; i++) {
          const url = await next;
          if (speakId.current !== id) return;
          if (!url) {
            // Doğal ses yok: kalan metni tarayıcı sesiyle oku
            return browserSpeak(list.slice(i).join(" "), onEnd);
          }
          if (i + 1 < list.length) next = fetchSpeech(list[i + 1]);
          await new Promise<void>((resolve) => {
            audio.onended = () => resolve();
            audio.onerror = () => resolve();
            audio.src = url;
            audio.play().catch(() => resolve());
          });
          URL.revokeObjectURL(url);
          if (speakId.current !== id) return;
        }
        setSpeaking(false);
        onEnd?.();
      })();
    },
    [browserSpeak],
  );

  const stopSpeaking = useCallback(() => {
    speakId.current++;
    playerRef.current?.stop();
    audioRef.current?.pause();
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  return { canListen, canSpeak, listening, speaking, listen, stopListening, cancelListening, speak, stopSpeaking, unlock };
}
