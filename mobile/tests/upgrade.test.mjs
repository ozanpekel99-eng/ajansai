// Sohbet limit kartı ve video önerisi yardımcılarının testleri: `npm test`
import assert from "node:assert/strict";
import test from "node:test";

import {
  freeFooter,
  limitFromError,
  limitFromReply,
  money,
  orderedPlans,
  planMeta,
  videoMeta,
  videoRouteParams,
  visibleLimit,
} from "../src/lib/upgrade.ts";

const plan = (id, name, extra = {}) => ({
  id,
  name,
  price: 20,
  currency: "USD",
  credits: 500,
  video_enabled: true,
  ads_enabled: true,
  examples: { messages: 500, images: 100, videos: { "720p": 15, "1080p": 13, "4k": 4 } },
  ...extra,
});
const status = (chat, images = 3) => ({
  chat: { used: 10 - chat, limit: 10, remaining: chat },
  images: { used: 3 - images, limit: 3, remaining: images },
});

test("paketler web ile aynı sırada, eksikler atlanır", () => {
  const pricing = { plans: { ajans: plan("ajans", "Advanced"), pro: plan("pro", "Pro"), baslangic: plan("baslangic", "Başlangıç") } };
  assert.deepEqual(orderedPlans(pricing).map((p) => p.id), ["baslangic", "pro", "ajans"]);
  assert.deepEqual(orderedPlans({ plans: { pro: plan("pro", "Pro") } }).map((p) => p.id), ["pro"]);
  assert.deepEqual(orderedPlans(null), []);
});

test("yanıttaki limit alanı ve 429 kart açar", () => {
  assert.equal(limitFromReply({ limit: "image" }), "image");
  assert.equal(limitFromReply({ limit: null }), null);
  assert.equal(limitFromReply({ limit: "bilinmeyen" }), null);
  assert.equal(limitFromReply(undefined), null);
  assert.equal(limitFromError(429, true), "chat");
  assert.equal(limitFromError(429, false), null); // ücretli sohbette 429 kart açmaz
  assert.equal(limitFromError(402, true), null);
});

test("mesaj hakkı biten ücretsiz kullanıcıya kart görünür", () => {
  assert.equal(visibleLimit(null, true, status(0)), "chat");
  assert.equal(visibleLimit(null, true, status(4)), null);
  assert.equal(visibleLimit(null, false, status(0)), null);
  assert.equal(visibleLimit("image", true, status(4)), "image");
  assert.equal(visibleLimit("video", false, null), "video");
  assert.equal(visibleLimit(null, true, null), null);
});

test("ücretsiz alt bilgi metni", () => {
  assert.equal(freeFooter(status(7, 2)), "Bugün 7 mesaj, bu ay 2 görsel hakkın kaldı");
  assert.equal(freeFooter(null), "Ücretsiz pakettesin");
});

test("fiyat ve paket özeti", () => {
  assert.equal(money(20, "USD"), "$20");
  assert.equal(money(499, "TRY"), "₺499");
  assert.equal(money(9.5, "EUR"), "€9,50");
  assert.equal(planMeta(plan("pro", "Pro")), "500 kredi · 100 görsel ya da 13 video");
  assert.equal(
    planMeta(plan("x", "X", { credits: 1000, examples: { messages: 1000, images: 200, videos: { "1080p": 0 } } })),
    "1.000 kredi · 200 görsel",
  );
});

test("video önerisi Üret ekranını hazır açar", () => {
  const v = { concept: "iced coffee pouring", aspect: "9:16", duration: 6, image_url: "https://blob/x.png", enabled: true };
  assert.equal(videoMeta(v), "9:16 · 6 sn · görselden başlar");
  assert.equal(videoMeta({ ...v, image_url: null }), "9:16 · 6 sn");
  assert.deepEqual(videoRouteParams(v), { tab: "video", konsept: "iced coffee pouring", gorsel: "https://blob/x.png" });
  assert.deepEqual(videoRouteParams({ ...v, image_url: null }).gorsel, "");
});
