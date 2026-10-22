"use client";

// Gerçek zamanlı sesli sohbet (konuşmadan konuşmaya): mikrofon sesi Vercel AI Gateway
// üzerinden modele akar, modelin sesi parça parça gelip anında çalınır. Kullanıcı
// konuşmaya başlayınca model susar (araya girme). Kredi dakika başı sunucuda düşülür.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "./api";
import { PcmPlayer } from "./voice";

const RATE = 24000;

export type RealtimeState = "idle" | "connecting" | "listening" | "speaking" | "error";

type Setup = { token: string; url: string; voice: string; instructions: string; credits_per_minute: number };

function toBase64(bytes: Uint8Array) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function fromBase64(b64: string) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Float32 (cihaz örnekleme hızı) → 24 kHz PCM16 */
function encode(input: Float32Array, fromRate: number): Uint8Array {
  const ratio = fromRate / RATE;
  const n = Math.floor(input.length / ratio);
  const out = new DataView(new ArrayBuffer(n * 2));
  for (let i = 0; i < n; i++) {
    const pos = i * ratio;
    const j = Math.floor(pos);
    const f = pos - j;
    const v = (input[j] ?? 0) * (1 - f) + (input[j + 1] ?? input[j] ?? 0) * f;
    const c = Math.max(-1, Math.min(1, v));
    out.setInt16(i * 2, c < 0 ? c * 0x8000 : c * 0x7fff, true);
  }
  return new Uint8Array(out.buffer);
}

export function useRealtimeVoice(opts: {
  onUserText?: (text: string) => void;
  onAssistantText?: (text: string) => void;
}) {
  const [state, setState] = useState<RealtimeState>("idle");
  const [error, setError] = useState("");
  const [partial, setPartial] = useState("");
  const optsRef = useRef(opts);
  optsRef.current = opts;
  const refs = useRef<{
    ws?: WebSocket;
    ctx?: AudioContext;
    stream?: MediaStream;
    proc?: ScriptProcessorNode;
    player?: PcmPlayer;
    tick?: ReturnType<typeof setInterval>;
    idle?: ReturnType<typeof setTimeout>;
    max?: ReturnType<typeof setTimeout>;
  }>({});

  const stop = useCallback((message?: string) => {
    const r = refs.current;
    if (r.tick) clearInterval(r.tick);
    if (r.idle) clearTimeout(r.idle);
    if (r.max) clearTimeout(r.max);
    try {
      if (r.ws && r.ws.readyState === WebSocket.OPEN) r.ws.send(JSON.stringify({ type: "session-close" }));
      r.ws?.close();
    } catch {
      // zaten kapalı
    }
    r.proc?.disconnect();
    r.stream?.getTracks().forEach((t) => t.stop());
    r.player?.stop();
    r.ctx?.close().catch(() => {});
    refs.current = {};
    setPartial("");
    if (message) {
      setError(message);
      setState("error");
    } else {
      setState("idle");
    }
  }, []);

  useEffect(() => () => stop(), [stop]);

  const start = useCallback(
    async (context = "") => {
      if (refs.current.ws) return;
      setError("");
      setState("connecting");
      // Ses bağlamı kullanıcı dokunuşunda açılmalı (mobil tarayıcılar)
      const AC = (window as any).AudioContext || (window as any).webkitAudioContext;
      const ctx: AudioContext = new AC();
      refs.current.ctx = ctx;
      ctx.resume().catch(() => {});
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
      } catch {
        return stop("Mikrofon izni verilmedi. Tarayıcı ayarlarından izin verebilirsin.");
      }
      refs.current.stream = stream;
      let setup: Setup;
      try {
        setup = await api<Setup>("/api/voice/realtime/token", { method: "POST", body: JSON.stringify({ context }) });
      } catch (e) {
        return stop(e instanceof ApiError ? e.message : "Sesli sohbet başlatılamadı.");
      }
      const player = new PcmPlayer(ctx);
      refs.current.player = player;
      const ws = new WebSocket(setup.url, ["ai-gateway-realtime.v1", `ai-gateway-auth.${setup.token}`]);
      refs.current.ws = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            type: "session-update",
            config: {
              instructions: setup.instructions,
              voice: setup.voice,
              outputModalities: ["audio"],
              inputAudioFormat: { type: "audio/pcm", rate: RATE },
              outputAudioFormat: { type: "audio/pcm", rate: RATE },
              turnDetection: { type: "server-vad", silenceDurationMs: 550, prefixPaddingMs: 300 },
              inputAudioTranscription: { language: "tr" },
              outputAudioTranscription: {},
            },
          }),
        );
        // Mikrofon → model
        const source = ctx.createMediaStreamSource(stream);
        const proc = ctx.createScriptProcessor(4096, 1, 1);
        const mute = ctx.createGain();
        mute.gain.value = 0;
        proc.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const pcm = encode(e.inputBuffer.getChannelData(0), ctx.sampleRate);
          ws.send(JSON.stringify({ type: "input-audio-append", audio: toBase64(pcm) }));
        };
        source.connect(proc);
        proc.connect(mute);
        mute.connect(ctx.destination);
        refs.current.proc = proc;
        setState("listening");
        // Dakika başı kredi; kredi bitince oturum kapanır
        refs.current.tick = setInterval(() => {
          api("/api/voice/realtime/tick", { method: "POST" }).catch((e) =>
            stop(e instanceof ApiError && e.status === 402 ? e.message : undefined),
          );
        }, 60_000);
        refs.current.max = setTimeout(() => stop(), 20 * 60_000);
      };

      let assistantText = "";
      ws.onmessage = (msg) => {
        let ev: any;
        try {
          ev = JSON.parse(typeof msg.data === "string" ? msg.data : "");
        } catch {
          return;
        }
        switch (ev.type) {
          case "audio-delta":
            if (ev.delta) {
              player.push(fromBase64(ev.delta));
              setState("speaking");
              if (refs.current.idle) clearTimeout(refs.current.idle);
              refs.current.idle = setTimeout(() => refs.current.ws && setState("listening"), player.remaining() + 150);
            }
            break;
          case "speech-started":
            // Kullanıcı konuşmaya başladı: modelin sesini kes
            player.stop();
            setState("listening");
            break;
          case "audio-transcript-delta":
            assistantText += ev.delta || "";
            setPartial(assistantText);
            break;
          case "audio-transcript-done": {
            const t = (ev.transcript || assistantText).trim();
            assistantText = "";
            setPartial("");
            if (t) optsRef.current.onAssistantText?.(t);
            break;
          }
          case "input-transcription-completed":
            if (ev.transcript?.trim()) optsRef.current.onUserText?.(ev.transcript.trim());
            break;
          case "error":
            if (ev.message) setError(ev.message);
            break;
          case "session-closed":
            stop();
            break;
        }
      };
      ws.onerror = () => stop("Sesli sohbet bağlantısı kesildi.");
      ws.onclose = () => refs.current.ws === ws && stop();
    },
    [stop],
  );

  return { state, error, partial, start, stop: () => stop(), active: state !== "idle" && state !== "error" };
}
