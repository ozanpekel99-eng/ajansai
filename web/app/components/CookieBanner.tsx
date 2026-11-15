"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CONSENT_OPEN_EVENT, readConsent, saveConsent, type Consent } from "../lib/consent";

/**
 * KVKK çerez onay bandı. Seçim yapılmadıysa ekranın altında küçük bir şerit olarak görünür
 * (sayfayı kapatmaz, kaydırmayı engellemez). "Kabul et" Meta Pikselini yükler, "Reddet" yüklemez.
 * Alt bilgideki "Çerez tercihleri" bağlantısı bandı yeniden açar.
 */
export default function CookieBanner() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (readConsent() === null) setOpen(true);
    const reopen = () => setOpen(true);
    window.addEventListener(CONSENT_OPEN_EVENT, reopen);
    return () => window.removeEventListener(CONSENT_OPEN_EVENT, reopen);
  }, []);

  if (!open) return null;

  const choose = (value: Consent) => {
    saveConsent(value);
    setOpen(false);
  };

  return (
    <div className="cookie-banner" role="region" aria-label="Çerez tercihleri">
      <p>
        Reklamlarımızın etkisini ölçmek için, onay verirsen Meta Pikseli çerezlerini kullanırız. Zorunlu olmayan çerezler
        onayın olmadan yüklenmez. <Link href="/gizlilik">Ayrıntılar</Link>
      </p>
      <div className="cookie-banner-actions">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => choose("denied")}>
          Reddet
        </button>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => choose("granted")}>
          Kabul et
        </button>
      </div>
    </div>
  );
}
