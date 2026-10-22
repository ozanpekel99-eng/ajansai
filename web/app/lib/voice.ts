"use client";

// Sesli sohbet: tarayıcının kendi konuşma tanıma (SpeechRecognition) ve sesli
// okuma (speechSynthesis) özellikleri. Ek sunucu maliyeti yoktur.

import { useCallback, useEffect, useRef, useState } from "react";

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

  useEffect(() => {
    setCanListen(!!recognitionCtor());
    setCanSpeak(typeof window !== "undefined" && "speechSynthesis" in window);
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

  const speak = useCallback((md: string, onEnd?: () => void) => {
    if (!("speechSynthesis" in window)) return onEnd?.();
    window.speechSynthesis.cancel();
    const text = speakableText(md).slice(0, 4000);
    if (!text) return onEnd?.();
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

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  return { canListen, canSpeak, listening, speaking, listen, stopListening, cancelListening, speak, stopSpeaking };
}
