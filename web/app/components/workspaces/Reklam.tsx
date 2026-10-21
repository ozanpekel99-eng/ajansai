"use client";

import { FormEvent, useEffect, useState } from "react";

import { api } from "../../lib/api";
import { useSession } from "../../lib/session";
import { EmptyResult, LockedNotice, WorkspaceProps } from "./common";

type AdAccount = { account_id: string; name: string; currency: string };

export default function ReklamWorkspace(_: WorkspaceProps) {
  const { usage, metaConnected, refresh } = useSession();
  const [accounts, setAccounts] = useState<AdAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<string[]>([]);

  useEffect(() => {
    if (!metaConnected) return;
    api<{ ad_accounts: AdAccount[] }>("/api/ads/meta/ad-accounts")
      .then((d) => {
        setAccounts(d.ad_accounts);
        if (d.ad_accounts[0]) setAccountId(d.ad_accounts[0].account_id);
      })
      .catch((e) => setError(e.message));
  }, [metaConnected]);

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
    setAccounts([]);
    refresh();
  };

  const createDraft = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/ads/meta/campaign-draft", {
        method: "POST",
        body: JSON.stringify({ ad_account_id: accountId, campaign_name: name }),
      });
      setCreated((c) => [name, ...c]);
      setName("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (usage && !usage.ads_enabled) {
    return <LockedNotice text="Meta reklam entegrasyonu Pro ve Ajans paketlerinde açılır." plan="pro" />;
  }

  return (
    <div className="workspace">
      {metaConnected ? (
        <form className="panel ws-panel" onSubmit={createDraft}>
          <h2>
            Yeni kampanya taslağı
            <button type="button" className="btn btn-ghost btn-sm" onClick={disconnect}>
              Bağlantıyı kaldır
            </button>
          </h2>
          <div className="field">
            <label htmlFor="r-account">Reklam hesabı</label>
            <select id="r-account" value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
              {accounts.map((a) => (
                <option key={a.account_id} value={a.account_id}>
                  {a.name} ({a.currency})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="r-name">Kampanya adı</label>
            <input id="r-name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Kasım buzdolabı kampanyası" />
          </div>
          <div className="generate">
            <button className="btn btn-primary btn-block" type="submit" disabled={busy || !accountId}>
              {busy ? "Taslak oluşturuluyor…" : "Taslak oluştur"}
            </button>
            <div className="cost">
              <span>Taslak duraklatılmış oluşturulur, harcama yapılmaz</span>
            </div>
          </div>
        </form>
      ) : (
        <div className="panel ws-panel">
          <h2>Meta hesabını bağla</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Kendi Meta Business hesabını bağlarsın. Reklam bütçesi senin hesabından harcanır; ajansAI kampanyayı sen onaylamadan
            yayına almaz.
          </p>
          <button className="btn btn-primary btn-block" onClick={connect}>
            Meta ile bağlan
          </button>
        </div>
      )}

      <section className="panel ws-panel result-area" aria-live="polite">
        <h2>Oluşturulan taslaklar</h2>
        {error && <div className="notice error">{error}</div>}
        {created.length ? (
          <div className="history">
            {created.map((c, i) => (
              <div className="history-item" key={i}>
                <span className="status-pill pending">Duraklatıldı</span>
                <span>{c}</span>
                <a className="when" href="https://adsmanager.facebook.com" target="_blank" rel="noreferrer">
                  Reklam Yöneticisi'nde aç
                </a>
              </div>
            ))}
          </div>
        ) : (
          <EmptyResult
            text={
              metaConnected
                ? "Bu oturumda oluşturduğun taslaklar burada listelenir."
                : "Hesabını bağladıktan sonra kampanya taslakların burada görünür."
            }
          />
        )}
      </section>
    </div>
  );
}
