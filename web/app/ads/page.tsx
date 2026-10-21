"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import Header from "../components/Header";
import { api } from "../lib/api";
import { useAuth } from "../lib/useAuth";

type AdAccount = { account_id: string; name: string; currency: string };

export default function Ads() {
  const { ready, usage } = useAuth();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [accounts, setAccounts] = useState<AdAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  const [campaignName, setCampaignName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ready || !usage?.ads_enabled) return;
    api<{ connected: boolean }>("/api/ads/meta/status")
      .then((d) => setConnected(d.connected))
      .catch((e) => setError(e.message));
  }, [ready, usage?.ads_enabled]);

  useEffect(() => {
    if (!connected) return;
    api<{ ad_accounts: AdAccount[] }>("/api/ads/meta/ad-accounts")
      .then((d) => {
        setAccounts(d.ad_accounts);
        if (d.ad_accounts[0]) setAccountId(d.ad_accounts[0].account_id);
      })
      .catch((e) => setError(e.message));
  }, [connected]);

  const connect = async () => {
    setError("");
    try {
      const d = await api<{ oauth_url: string }>("/api/ads/meta/connect");
      window.location.href = d.oauth_url;
    } catch (e: any) {
      setError(e.message);
    }
  };

  const disconnect = async () => {
    await api("/api/ads/meta/connection", { method: "DELETE" });
    setConnected(false);
    setAccounts([]);
  };

  const createDraft = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api("/api/ads/meta/campaign-draft", {
        method: "POST",
        body: JSON.stringify({ ad_account_id: accountId, campaign_name: campaignName }),
      });
      setMessage("Kampanya taslağı DURAKLATILMIŞ olarak oluşturuldu. Meta Reklam Yöneticisi'nden kontrol edip yayına alabilirsin.");
      setCampaignName("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!ready) return null;

  return (
    <div className="page">
      <Header usage={usage} />

      <section className="hero">
        <h1>Reklamların</h1>
        <p>Meta reklam hesabını bağla, kampanya taslaklarını buradan oluştur. Taslaklar sen onaylamadan yayına girmez.</p>
      </section>

      {usage && !usage.ads_enabled && (
        <div className="notice">
          Reklam entegrasyonu Pro ve Ajans paketlerinde açılır. <Link href="/pricing">Paketleri gör →</Link>
        </div>
      )}

      {error && <div className="notice error">{error}</div>}
      {message && <div className="notice">{message}</div>}

      {usage?.ads_enabled && connected === false && (
        <div className="ads-panel">
          <h2>Meta hesabını bağla</h2>
          <p>Kendi Meta Business hesabını bağlarsın; reklam bütçesi senin hesabından harcanır.</p>
          <button className="primary" onClick={connect}>
            Meta ile bağlan
          </button>
        </div>
      )}

      {usage?.ads_enabled && connected && (
        <>
          <form className="ads-panel" onSubmit={createDraft}>
            <h2>Yeni kampanya taslağı</h2>
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
              {accounts.map((a) => (
                <option key={a.account_id} value={a.account_id}>
                  {a.name} ({a.currency})
                </option>
              ))}
            </select>
            <input
              required
              value={campaignName}
              onChange={(e) => setCampaignName(e.target.value)}
              placeholder="Kampanya adı, ör. Yaz Kahve Kampanyası"
            />
            <button className="primary" type="submit" disabled={busy || !accountId}>
              {busy ? "Oluşturuluyor…" : "Taslak oluştur"}
            </button>
          </form>
          <button className="link-button" onClick={disconnect}>
            Meta bağlantısını kaldır
          </button>
        </>
      )}
    </div>
  );
}
