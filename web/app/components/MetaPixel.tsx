"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { CONSENT_EVENT, readConsent, type Consent } from "../lib/consent";
import { META_PIXEL_ID, track } from "../lib/pixel";

type Fbq = (...args: unknown[]) => void;

/**
 * Meta Pikseli (KVKK): betik yalnızca kullanıcı çerez bandında "Kabul et" dediyse yüklenir.
 * Onay sonradan geri çekilirse `fbq('consent','revoke')` ile gönderim durdurulur; yeniden
 * verilirse `fbq('consent','grant')`. Yüklendikten sonra her sayfa geçişinde PageView gönderir.
 */
export default function MetaPixel() {
  const pathname = usePathname();
  const first = useRef(true);
  const [consent, setConsent] = useState<Consent | null>(null);
  const [load, setLoad] = useState(false);

  useEffect(() => {
    const apply = (value: Consent | null) => {
      setConsent(value);
      if (value === "granted") setLoad(true);
      const fbq = (window as unknown as { fbq?: Fbq }).fbq;
      if (fbq && value) {
        try {
          fbq("consent", value === "granted" ? "grant" : "revoke");
        } catch {
          // piksel engellendiyse sessizce geç
        }
      }
    };
    apply(readConsent());
    const onChange = (e: Event) => apply((e as CustomEvent<Consent>).detail ?? readConsent());
    window.addEventListener(CONSENT_EVENT, onChange);
    return () => window.removeEventListener(CONSENT_EVENT, onChange);
  }, []);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (consent === "granted") track("PageView");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (!load) return null;
  return (
    <Script id="meta-pixel" strategy="afterInteractive">
      {`!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('consent','grant');fbq('init','${META_PIXEL_ID}');fbq('track','PageView');`}
    </Script>
  );
}
