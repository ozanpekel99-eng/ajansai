// "Reklam ver" kısayolu testleri. Çalıştır: cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { adHref, forgetAdShortcut, parseAdShortcut, readAdShortcut, rememberAdShortcut } from "../app/lib/adShortcut.ts";

const memory = () => {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), m };
};

test("adHref görsel ve video bağlantısı üretir, açıklamayı kısaltır", () => {
  const img = adHref("https://cdn.ajansai.tr/a b.png?x=1&y=2", "image", "  Kış indirimi  ");
  assert.ok(img.startsWith("/araclar/reklam?"));
  const q = new URLSearchParams(img.split("?")[1]);
  assert.equal(q.get("medya"), "https://cdn.ajansai.tr/a b.png?x=1&y=2");
  assert.equal(q.get("tur"), "gorsel");
  assert.equal(q.get("konsept"), "Kış indirimi");

  const vid = new URLSearchParams(adHref("https://x.tr/v.mp4", "video", "x".repeat(500)).split("?")[1]);
  assert.equal(vid.get("tur"), "video");
  assert.equal(vid.get("konsept").length, 200);

  assert.equal(new URLSearchParams(adHref("https://x.tr/a.png", "image").split("?")[1]).has("konsept"), false);
});

test("parseAdShortcut adHref ile gidip gelir", () => {
  const href = adHref("https://cdn.ajansai.tr/v.mp4", "video", "Tanıtım");
  assert.deepEqual(parseAdShortcut(href.slice(href.indexOf("?"))), { url: "https://cdn.ajansai.tr/v.mp4", kind: "video", concept: "Tanıtım" });
});

test("parseAdShortcut yalnızca https kabul eder", () => {
  for (const bad of ["javascript:alert(1)", "http://x.tr/a.png", "data:image/png;base64,AAA", "", "https://"]) {
    assert.equal(parseAdShortcut(`?medya=${encodeURIComponent(bad)}&tur=gorsel`), null, bad);
  }
  assert.equal(parseAdShortcut("?yayin=1"), null);
});

test("tür verilmezse dosya uzantısından anlaşılır", () => {
  assert.equal(parseAdShortcut("?medya=" + encodeURIComponent("https://x.tr/a.MOV?t=1")).kind, "video");
  assert.equal(parseAdShortcut("?medya=" + encodeURIComponent("https://x.tr/a.png")).kind, "image");
  assert.equal(parseAdShortcut("?tur=gorsel&medya=" + encodeURIComponent("https://x.tr/a.mp4")).kind, "image");
});

test("Meta bağlantısı dönüşünde oturumdaki kısayol okunur, sonra silinir", () => {
  const kv = memory();
  const s = { url: "https://x.tr/a.png", kind: "image", concept: "Kahvaltı menüsü" };
  rememberAdShortcut(s, kv);
  assert.deepEqual(readAdShortcut("", kv), s);
  assert.deepEqual(readAdShortcut("?code=abc", kv), s, "OAuth parametreleri kısayolu bozmaz");
  // Adres satırındaki kısayol öncelikli
  assert.equal(readAdShortcut("?medya=" + encodeURIComponent("https://x.tr/b.mp4"), kv).url, "https://x.tr/b.mp4");
  forgetAdShortcut(kv);
  assert.equal(readAdShortcut("", kv), null);
});

test("bozuk ya da tehlikeli kayıt yok sayılır, depolama yoksa hata vermez", () => {
  const kv = memory();
  kv.setItem("ajansai_reklam_kisayol", "{bozuk");
  assert.equal(readAdShortcut("", kv), null);
  kv.setItem("ajansai_reklam_kisayol", JSON.stringify({ url: "javascript:alert(1)", kind: "image" }));
  assert.equal(readAdShortcut("", kv), null);
  kv.setItem("ajansai_reklam_kisayol", JSON.stringify({ url: "https://x.tr/a.png", kind: "ses" }));
  assert.equal(readAdShortcut("", kv), null);

  const broken = { getItem: () => { throw new Error("kapalı"); }, setItem: () => { throw new Error("kapalı"); }, removeItem: () => { throw new Error("kapalı"); } };
  assert.doesNotThrow(() => rememberAdShortcut({ url: "https://x.tr/a.png", kind: "image", concept: "" }, broken));
  assert.equal(readAdShortcut("", broken), null);
  assert.doesNotThrow(() => forgetAdShortcut(broken));
  assert.equal(readAdShortcut("", null), null);
});
