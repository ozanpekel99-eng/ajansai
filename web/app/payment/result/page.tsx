"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { api, getToken } from "../../lib/api";

type Status = "success" | "failure" | "pending";

function Result() {
  const params = useSearchParams();
  const paymentId = params.get("payment_id");
  const [status, setStatus] = useState<Status>((params.get("status") as Status) || "pending");
  const [planName, setPlanName] = useState("");

  useEffect(() => {
    if (!paymentId || !getToken()) return;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;

    // Sonucu her zaman backend'den teyit ediyoruz (adres çubuğundaki status'a güvenmiyoruz).
    const check = async () => {
      try {
        const data = await api<{ status: Status; plan_name: string }>(`/api/payments/${paymentId}`);
        setStatus(data.status);
        setPlanName(data.plan_name);
        if (data.status === "pending" && tries++ < 10) timer = setTimeout(check, 3000);
      } catch {
        // sayfadaki mevcut durum gösterilmeye devam eder
      }
    };
    check();
    return () => clearTimeout(timer);
  }, [paymentId]);

  return (
    <div className="panel result-card">
      <img src="/logo-on-dark.png" alt="ajansAI" className="logo" />
      {status === "success" && (
        <>
          <h1>Ödeme alındı</h1>
          <p>{planName ? `${planName} paketin` : "Paketin"} açıldı ve 30 gün boyunca geçerli.</p>
          <Link className="btn btn-primary btn-block" href="/araclar">İçerik üretmeye başla</Link>
        </>
      )}
      {status === "failure" && (
        <>
          <h1>Ödeme tamamlanamadı</h1>
          <p>Kartından para çekilmedi. Farklı bir kartla tekrar deneyebilirsin.</p>
          <Link className="btn btn-light btn-block" href="/paketler">Paketlere dön</Link>
        </>
      )}
      {status === "pending" && (
        <>
          <h1>Ödeme kontrol ediliyor…</h1>
          <p>Bu birkaç saniye sürebilir. Sayfa kendiliğinden güncellenecek.</p>
        </>
      )}
    </div>
  );
}

export default function PaymentResult() {
  return (
    <div className="result-page">
      <Suspense fallback={null}>
        <Result />
      </Suspense>
    </div>
  );
}
