"use client";

// Sohbet geçmişi: giriş yapmış kullanıcıda sunucuda (her cihazdan görünür), misafirde bu tarayıcıda.

import { api, getToken } from "./api";
import type { Conversation } from "../components/ChatPanel";

export type ChatSummary = { id: string; title: string; at: number };

const LOCAL_KEY = "ajansai_chats";
const MIGRATED_KEY = "ajansai_chats_migrated";
export const CHATS_EVENT = "ajansai:chats";

/** Şu an ekranda açık olan sohbet (adres çubuğu güncellenince yeniden yüklenmesin diye). */
let shownId: string | null = null;
export function setShownChat(id: string | null) {
  shownId = id;
}
export function isShownChat(id: string) {
  return shownId === id;
}

export function localChats(): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveLocal(list: Conversation[]) {
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(list.slice(0, 30)));
  } catch {
    // depolama kapalıysa sohbet yalnızca bu sekmede kalır
  }
}

function notify(activeId?: string) {
  window.dispatchEvent(new CustomEvent(CHATS_EVENT, { detail: { activeId } }));
}

/** Bu tarayıcıdaki eski sohbetleri bir kez hesaba taşır. */
async function migrate() {
  try {
    if (localStorage.getItem(MIGRATED_KEY)) return;
    const list = localChats();
    for (const c of list.slice(0, 30)) {
      await api(`/api/chats/${encodeURIComponent(c.id)}`, { method: "PUT", body: JSON.stringify({ title: c.title, messages: c.messages }) });
    }
    localStorage.setItem(MIGRATED_KEY, "1");
  } catch {
    // bir sonraki açılışta tekrar denenir
  }
}

export async function listChats(): Promise<ChatSummary[]> {
  if (!getToken()) return localChats().map((c) => ({ id: c.id, title: c.title, at: c.at }));
  await migrate();
  const rows = await api<{ id: string; title: string; updated_at: string }[]>("/api/chats?limit=60");
  return rows.map((r) => ({ id: r.id, title: r.title, at: Date.parse(r.updated_at) }));
}

export async function getChat(id: string): Promise<Conversation | null> {
  if (getToken()) {
    try {
      const c = await api<{ id: string; title: string; messages: Conversation["messages"]; updated_at: string }>(
        `/api/chats/${encodeURIComponent(id)}`,
      );
      return { id: c.id, title: c.title, at: Date.parse(c.updated_at), messages: c.messages };
    } catch {
      // sunucuda yoksa yereldeki kopyaya bak
    }
  }
  return localChats().find((c) => c.id === id) || null;
}

export async function saveChat(conv: Conversation) {
  shownId = conv.id;
  saveLocal([conv, ...localChats().filter((c) => c.id !== conv.id)]);
  if (getToken()) {
    try {
      await api(`/api/chats/${encodeURIComponent(conv.id)}`, {
        method: "PUT",
        body: JSON.stringify({ title: conv.title, messages: conv.messages }),
      });
    } catch {
      // ağ hatası: yerel kopya duruyor, sonraki mesajda tekrar kaydedilir
    }
  }
  notify(conv.id);
}

export async function deleteChat(id: string) {
  saveLocal(localChats().filter((c) => c.id !== id));
  if (getToken()) {
    try {
      await api(`/api/chats/${encodeURIComponent(id)}`, { method: "DELETE" });
    } catch {
      // yoksay
    }
  }
  notify();
}
