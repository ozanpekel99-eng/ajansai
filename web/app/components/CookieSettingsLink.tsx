"use client";

import { openConsentSettings } from "../lib/consent";

/** Alt bilgide çerez bandını yeniden açan bağlantı (seçimi değiştirmek için). */
export default function CookieSettingsLink() {
  return (
    <button type="button" className="link-button" onClick={openConsentSettings}>
      Çerez tercihleri
    </button>
  );
}
