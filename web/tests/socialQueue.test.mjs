// Yayın kuyruğu (yönetici onay sayfası) yardımcı testleri. Çalıştır: cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  captionWarnings,
  countByStatus,
  formatLocal,
  fromInputValue,
  groupByWeek,
  hashtagCount,
  isVideo,
  normalizeMediaBase,
  parsePlan,
  statusLabel,
  toInputValue,
  upcomingMonday,
  weekFromPath,
  weekLabel,
} from "../app/lib/socialQueue.ts";

test("upcomingMonday: pazartesi aynı gün, diğer günler sonraki pazartesi", () => {
  assert.equal(upcomingMonday(new Date(2026, 10, 23)), "2026-11-23"); // pazartesi
  assert.equal(upcomingMonday(new Date(2026, 10, 24)), "2026-11-30"); // salı
  assert.equal(upcomingMonday(new Date(2026, 10, 29)), "2026-11-30"); // pazar
  assert.equal(upcomingMonday(new Date(2026, 11, 29)), "2027-01-04"); // yıl dönümü
});

test("datetime-local dönüşümleri gidip gelir", () => {
  assert.equal(toInputValue("2026-11-24 12:30"), "2026-11-24T12:30");
  assert.equal(fromInputValue("2026-11-24T12:30"), "2026-11-24 12:30");
  assert.equal(fromInputValue("2026-11-24T12:30:00"), "2026-11-24 12:30");
  assert.equal(fromInputValue(""), null);
  assert.equal(fromInputValue("24.11.2026 12:30"), null);
});

test("formatLocal ve weekLabel Türkçe gün/ay adı yazar", () => {
  assert.equal(formatLocal("2026-11-24 12:30"), "Salı 24 Kasım, 12:30");
  assert.equal(formatLocal("2026-11-29 20:30"), "Pazar 29 Kasım, 20:30");
  assert.equal(formatLocal("bozuk"), "bozuk");
  assert.equal(weekLabel("2026-11-23"), "23 Kasım 2026 haftası");
});

test("etiket sayımı Türkçe harfleri kapsar, uyarılar backend sınırlarıyla aynı", () => {
  assert.equal(hashtagCount("#ajansAI #işletme #sosyalmedyayönetimi metin #kobi"), 4);
  assert.deepEqual(captionWarnings("Merhaba #ajansAI"), []);
  assert.deepEqual(captionWarnings("   "), ["Açıklama boş."]);
  assert.match(captionWarnings("a".repeat(2201))[0], /2200/);
  const many = Array.from({ length: 31 }, (_, i) => `#e${i}`).join(" ");
  assert.match(captionWarnings(many)[0], /30 etiket/);
});

test("isVideo uzantıya bakar, sorgu dizesini yok sayar", () => {
  assert.equal(isVideo("https://x.tr/r1.mp4?v=2"), true);
  assert.equal(isVideo("https://x.tr/r1.MOV"), true);
  assert.equal(isVideo("https://x.tr/g1.png"), false);
});

const post = (id, week, at, status = "pending", idx = 0) => ({
  id, week, idx, kind: "image", title: id, target: "", caption: "x", media: [], scheduled_at: at,
  scheduled_local: at, status, ig_media_id: null, error: null, approved_by: null, problems: [],
});

test("groupByWeek en yeni haftayı öne alır, hafta içinde zamana göre sıralar", () => {
  const groups = groupByWeek([
    post("b", "2026-11-16", "2026-11-17T09:30:00Z"),
    post("d", "2026-11-23", "2026-11-25T09:30:00Z", "pending", 2),
    post("c", "2026-11-23", "2026-11-24T09:30:00Z", "approved", 1),
    post("a", "2026-11-16", "2026-11-16T09:30:00Z"),
  ]);
  assert.deepEqual(groups.map((g) => g.week), ["2026-11-23", "2026-11-16"]);
  assert.deepEqual(groups[0].posts.map((p) => p.id), ["c", "d"]);
  assert.deepEqual(groups[1].posts.map((p) => p.id), ["a", "b"]);
  assert.deepEqual(countByStatus(groups[0].posts), { approved: 1, pending: 1 });
  assert.equal(statusLabel("approved").text, "Onaylandı");
  assert.equal(statusLabel("bilinmeyen").text, "bilinmeyen");
});

test("parsePlan geçerli planı okur, eksik alanları Türkçe bildirir", () => {
  const row = { day: "Salı 24 Kasım", time: "12:30", type: "Gönderi", caption: "Merhaba", files: ["g1.png"] };
  assert.equal(parsePlan(JSON.stringify([row])).length, 1);
  assert.equal(parsePlan(JSON.stringify({ posts: [row] })).length, 1);
  assert.throws(() => parsePlan("{bozuk"), /geçerli bir JSON değil/);
  assert.throws(() => parsePlan("[]"), /gönderi listesi/);
  assert.throws(() => parsePlan(JSON.stringify([{ ...row, time: "" }])), /1\. satırda 'time' eksik/);
  assert.throws(() => parsePlan(JSON.stringify([row, { ...row, files: [] }])), /2\. satırda dosya listesi/);
});

test("weekFromPath ve normalizeMediaBase", () => {
  assert.equal(weekFromPath("marketing/2026-11-23/plan.json"), "2026-11-23");
  assert.equal(weekFromPath("plan.json"), null);
  assert.deepEqual(normalizeMediaBase(""), { value: null });
  assert.deepEqual(normalizeMediaBase(" https://cdn.ajansai.tr/m/2026-11-23/ "), { value: "https://cdn.ajansai.tr/m/2026-11-23" });
  assert.equal(normalizeMediaBase("http://x.tr").error, "Dosya adresi https:// ile başlamalı.");
});
