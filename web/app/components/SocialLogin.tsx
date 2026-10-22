"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, api, setToken } from "../lib/api";

type Providers = { google_client_id: string | null; apple_client_id: string | null };

declare global {
  interface Window {
    google?: any;
    AppleID?: any;
  }
}

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(src));
    document.head.appendChild(s);
  });
}

/** Google ve Apple ile giriş/kayıt. Hesap yoksa aynı anda oluşturulur. */
export default function SocialLogin({ onDone }: { onDone: () => void }) {
  const [providers, setProviders] = useState<Providers | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const googleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Providers>("/api/auth/providers")
      .then(setProviders)
      .catch(() => setProviders({ google_client_id: null, apple_client_id: null }));
  }, []);

  const finish = async (path: string, body: object) => {
    setBusy(true);
    setError("");
    try {
      const data = await api<{ token: string }>(path, { method: "POST", body: JSON.stringify(body) });
      setToken(data.token);
      onDone();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const id = providers?.google_client_id;
    if (!id) return;
    loadScript("https://accounts.google.com/gsi/client")
      .then(() => {
        window.google.accounts.id.initialize({
          client_id: id,
          callback: (resp: { credential: string }) => finish("/api/auth/google", { credential: resp.credential }),
          ux_mode: "popup",
        });
        if (googleRef.current) {
          window.google.accounts.id.renderButton(googleRef.current, {
            theme: "filled_black",
            size: "large",
            shape: "rectangular",
            text: "continue_with",
            locale: "tr",
            width: googleRef.current.offsetWidth || 360,
          });
        }
      })
      .catch(() => setError("Google girişi yüklenemedi."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providers?.google_client_id]);

  useEffect(() => {
    const id = providers?.apple_client_id;
    if (!id) return;
    loadScript("https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/tr_TR/appleid.auth.js")
      .then(() =>
        window.AppleID.auth.init({
          clientId: id,
          scope: "name email",
          redirectURI: `${window.location.origin}/login`,
          usePopup: true,
        }),
      )
      .catch(() => setError("Apple girişi yüklenemedi."));
  }, [providers?.apple_client_id]);

  const apple = async () => {
    try {
      const r = await window.AppleID.auth.signIn();
      const n = r.user?.name;
      await finish("/api/auth/apple", {
        id_token: r.authorization.id_token,
        name: n ? `${n.firstName || ""} ${n.lastName || ""}`.trim() : "",
      });
    } catch (e: any) {
      if (e?.error !== "popup_closed_by_user") setError("Apple ile giriş tamamlanamadı.");
    }
  };

  if (!providers || (!providers.google_client_id && !providers.apple_client_id)) return null;

  return (
    <div className="social">
      {providers.google_client_id && <div ref={googleRef} className="google-btn" />}
      {providers.apple_client_id && (
        <button type="button" className="btn btn-light btn-block apple-btn" onClick={apple} disabled={busy}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path
              fill="currentColor"
              d="M16.4 12.6c0-2.4 2-3.6 2.1-3.7-1.1-1.7-2.9-1.9-3.5-1.9-1.5-.2-2.9.9-3.7.9-.8 0-1.9-.9-3.2-.8-1.6 0-3.1 1-4 2.4-1.7 3-.4 7.4 1.2 9.8.8 1.2 1.8 2.5 3 2.4 1.2 0 1.7-.8 3.1-.8 1.5 0 1.9.8 3.2.8 1.3 0 2.2-1.2 3-2.4.9-1.4 1.3-2.7 1.3-2.8-.1 0-2.5-1-2.5-3.9zM14 5.4c.7-.8 1.1-1.9 1-3-1 0-2.1.7-2.8 1.5-.6.7-1.2 1.8-1 2.9 1.1.1 2.1-.6 2.8-1.4z"
            />
          </svg>
          Apple ile devam et
        </button>
      )}
      {error && <div className="notice error">{error}</div>}
      <div className="divider">
        <span>veya e-postayla</span>
      </div>
    </div>
  );
}
