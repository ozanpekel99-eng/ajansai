// "Reklam ver" kısayolu yardımcılarının testleri: `npm test`
import assert from "node:assert/strict";
import test from "node:test";

import { adAction, adPath, adWebUrl, canAdvertise } from "../src/lib/adShortcut.ts";

const IMG = "https://cdn.ajansai.tr/u/1/gorsel.png?v=2";
const VID = "https://cdn.ajansai.tr/u/1/video.mp4";

test("web ile aynı sorgu biçimi", () => {
  const q = new URLSearchParams(adPath(IMG, "image", "Kasım indirimi").split("?")[1]);
  assert.equal(adPath(IMG, "image").split("?")[0], "/araclar/reklam");
  assert.equal(q.get("medya"), IMG);
  assert.equal(q.get("tur"), "gorsel");
  assert.equal(q.get("konsept"), "Kasım indirimi");
  assert.equal(new URLSearchParams(adPath(VID, "video").split("?")[1]).get("tur"), "video");
});

test("boş açıklama eklenmez, uzun açıklama kısaltılır", () => {
  assert.ok(!adPath(IMG, "image", "   ").includes("konsept"));
  const long = new URLSearchParams(adPath(IMG, "image", "a ".repeat(400)).split("?")[1]).get("konsept");
  assert.ok(long.length <= 200);
  assert.ok(!long.includes("  "));
});

test("tam web adresi", () => {
  assert.ok(adWebUrl(VID, "video").startsWith("https://www.ajansai.tr/araclar/reklam?"));
  assert.ok(adWebUrl(VID, "video", "", "https://ornek.tr/").startsWith("https://ornek.tr/araclar/reklam?"));
});

test("yalnızca https dosyalar", () => {
  assert.equal(canAdvertise(IMG), true);
  assert.equal(canAdvertise("http://x.tr/a.png"), false);
  assert.equal(canAdvertise("file:///tmp/a.png"), false);
  assert.equal(canAdvertise(""), false);
  assert.equal(canAdvertise(null), false);
});

test("paket yoksa paketlere, varsa web'e", () => {
  assert.deepEqual(adAction(IMG, "image", "", false), { type: "upgrade" });
  assert.deepEqual(adAction(IMG, "image", "", undefined), { type: "upgrade" });
  assert.deepEqual(adAction(null, "image", "", true), { type: "invalid" });
  const a = adAction(VID, "video", "Reels", true);
  assert.equal(a.type, "open");
  assert.equal(new URLSearchParams(a.url.split("?")[1]).get("medya"), VID);
});
