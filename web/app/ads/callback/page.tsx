"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { api } from "../../lib/api";

function Callback() {
  const params = useSearchParams();
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [error, setError] = useState("");
  const sent = useRef(false);

  useEffect(() => {
    // Meta kodu tek kullanımlık: geliştirme modunda effect iki kez çalışsa da bir kez gönder.
    if (sent.current) return;
    sent.current = true;
    const code = params.get("code");
    const oauthState = params.get("state");
    if (!code || !oauthState) {
      setState("error");
      setError(params.get("error_description") || "Meta bağlantısı iptal edildi.");
      return;
    }
    api("/api/ads/meta/callback", { method: "POST", body: JSON.stringify({ code, state: oauthState }) })
      .then(() => {
        setState("done");
        setTimeout(() => (window.location.href = "/ads"), 1500);
      })
      .catch((e) => {
        setState("error");
        setError(e.message);
      });
  }, [params]);

  return (
    <div className="result-card">
      {state === "working" && <h1>Meta hesabın bağlanıyor…</h1>}
      {state === "done" && <h1>Meta hesabın bağlandı ✓</h1>}
      {state === "error" && (
        <>
          <h1>Bağlantı kurulamadı</h1>
          <p>{error}</p>
          <Link href="/ads">Tekrar dene →</Link>
        </>
      )}
    </div>
  );
}

export default function MetaCallback() {
  return (
    <div className="page">
      <Suspense fallback={null}>
        <Callback />
      </Suspense>
    </div>
  );
}
