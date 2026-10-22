"use client";

// Sesli sohbet: tarayıcının kendi konuşma tanıma (SpeechRecognition) ve sesli
// okuma (speechSynthesis) özellikleri. Ek sunucu maliyeti yoktur.

import { useCallback, useEffect, useRef, useState } from "react";

import { API_URL, getToken } from "./api";

// Kısa sessiz MP3: iOS'ta ses çalabilmek için kullanıcı dokunuşunda bir kez çalınır.
const SILENT =
  "data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYwLjE2LjEwMAAAAAAAAAAAAAAA//NwwAAAAAAAAAAAAEluZm8AAAAPAAAABgAAAykAWlpaWlpaWlpaWlpaWlpaWnt7e3t7e3t7e3t7e3t7e3t7nJycnJycnJycnJycnJycnL29vb29vb29vb29vb29vb293t7e3t7e3t7e3t7e3t7e3t7/////////////////////AAAAAExhdmM2MC4zMQAAAAAAAAAAAAAAACQCowAAAAAAAAMpso+sIAAAAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NCxKMAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NAxKQAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/80LEowAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVU=";

/** Metni, sesli okumada beklemeyi kısaltmak için cümle sınırlarından parçalara böler. */
function chunks(text: string, max = 380): string[] {
  const parts = text.match(/[^.!?…]+[.!?…]*\s*/g) || [text];
  const out: string[] = [];
  let cur = "";
  for (const p of parts) {
    if ((cur + p).length > max && cur) {
      out.push(cur.trim());
      cur = "";
    }
    cur += p;
  }
  if (cur.trim()) out.push(cur.trim());
  // İlk parça kısa olsun ki ses hızlı başlasın
  if (out[0] && out[0].length > 160) {
    const first = out[0];
    const cut = first.lastIndexOf(" ", 160);
    if (cut > 60) out.splice(0, 1, first.slice(0, cut), first.slice(cut + 1));
  }
  return out;
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
  }, []);

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
      window.speechSynthesis?.cancel();
      if (!text) return onEnd?.();
      if (!audioRef.current) audioRef.current = new Audio();
      const audio = audioRef.current;
      const list = chunks(text);
      setSpeaking(true);

      (async () => {
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
    audioRef.current?.pause();
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  return { canListen, canSpeak, listening, speaking, listen, stopListening, cancelListening, speak, stopSpeaking, unlock };
}
