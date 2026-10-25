// Çerez onayı birim testleri: `npm test` (Node'un yerleşik test koşucusu; ek paket gerekmez).
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

function fakeWindow({ blocked = false } = {}) {
  const store = new Map();
  const events = [];
  globalThis.window = {
    localStorage: {
      getItem: (k) => {
        if (blocked) throw new Error("SecurityError");
        return store.has(k) ? store.get(k) : null;
      },
      setItem: (k, v) => {
        if (blocked) throw new Error("SecurityError");
        store.set(k, String(v));
      },
    },
    dispatchEvent: (e) => events.push(e),
  };
  return { store, events };
}

let mod;
let n = 0;
beforeEach(async () => {
  // her testte modülü taze yükle (bellekteki oturum seçimi sıfırlansın)
  mod = await import(`../app/lib/consent.ts?t=${n++}`);
});

test("seçim yokken onay yok sayılır", () => {
  fakeWindow();
  assert.equal(mod.readConsent(), null);
});

test("geçersiz kayıtlı değer onay sayılmaz", () => {
  const { store } = fakeWindow();
  store.set(mod.CONSENT_KEY, "evet");
  assert.equal(mod.readConsent(), null);
  assert.equal(mod.parseConsent("granted"), "granted");
  assert.equal(mod.parseConsent("denied"), "denied");
  assert.equal(mod.parseConsent(undefined), null);
});

test("Kabul et: localStorage'a yazılır ve olay yayınlanır", () => {
  const { store, events } = fakeWindow();
  mod.saveConsent("granted");
  assert.equal(store.get(mod.CONSENT_KEY), "granted");
  assert.equal(mod.readConsent(), "granted");
  assert.equal(events.length, 1);
  assert.equal(events[0].type, mod.CONSENT_EVENT);
  assert.equal(events[0].detail, "granted");
});

test("Reddet sonra Kabul et: son seçim geçerli", () => {
  fakeWindow();
  mod.saveConsent("denied");
  assert.equal(mod.readConsent(), "denied");
  mod.saveConsent("granted");
  assert.equal(mod.readConsent(), "granted");
});

test("depolama engelliyse seçim bu oturumda bellekte tutulur", () => {
  const { events } = fakeWindow({ blocked: true });
  assert.equal(mod.readConsent(), null);
  mod.saveConsent("granted");
  assert.equal(mod.readConsent(), "granted");
  assert.equal(events.length, 1);
});

test("sunucuda (window yok) onay yok sayılır", () => {
  delete globalThis.window;
  assert.equal(mod.readConsent(), null);
  assert.doesNotThrow(() => mod.saveConsent("granted"));
});

test("çerez tercihleri bağlantısı bandı açma olayını yayınlar", () => {
  const { events } = fakeWindow();
  mod.openConsentSettings();
  assert.equal(events[0].type, mod.CONSENT_OPEN_EVENT);
});
