"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import SocialLogin from "../components/SocialLogin";
import { api, setToken } from "../lib/api";

export default function Login() {
  const mode = "login" as "login" | "register";
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const update = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const body =
        mode === "register"
          ? { name: form.name, email: form.email, password: form.password }
          : { email: form.email, password: form.password };
      const data = await api<{ token: string }>(`/api/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setToken(data.token);
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth">
      <div className="auth-form">
        <img src="/logo-on-dark.png" alt="ajansAI" className="logo" />
        <h1>{mode === "login" ? "Tekrar hoş geldin" : "Hesabını oluştur"}</h1>
        <p>
          {mode === "login"
            ? "Sohbetlerine, görsellerine ve paketine ulaşmak için giriş yap."
            : ""}
        </p>

        <SocialLogin onDone={() => (window.location.href = "/")} />

        <form onSubmit={submit}>
          {mode === "register" && (
            <div className="field">
              <label htmlFor="l-name">Ad soyad</label>
              <input id="l-name" value={form.name} onChange={(e) => update("name", e.target.value)} autoComplete="name" />
            </div>
          )}
          <div className="field">
            <label htmlFor="l-email">E-posta</label>
            <input id="l-email" required type="email" value={form.email} onChange={(e) => update("email", e.target.value)} autoComplete="email" />
          </div>
          <div className="field">
            <label htmlFor="l-pass">Şifre</label>
            <input
              id="l-pass"
              required
              type="password"
              minLength={mode === "register" ? 8 : undefined}
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder={mode === "register" ? "En az 8 karakter" : ""}
            />
          </div>
          {error && <div className="notice error">{error}</div>}
          <button className="btn btn-primary btn-block" type="submit" disabled={loading} style={{ marginTop: 8 }}>
            {loading ? "Bekle…" : mode === "login" ? "Giriş yap" : "Hesap oluştur"}
          </button>
        </form>

        <div className="switch-link">
          <a href="/ucretsiz">Üye olmadan dene</a>
        </div>

        <div className="switch-link">
          Hesabın yok mu? <Link href="/kayit">Üye ol</Link>
        </div>
      </div>

      <div className="auth-art" aria-hidden="true">
        <div className="tile" style={{ top: "12%", left: "14%", width: 120, height: 120 }} />
        <div className="tile w" style={{ top: "20%", left: "52%", width: 64, height: 64 }} />
        <div className="tile" style={{ top: "38%", left: "34%", width: 180, height: 90 }} />
        <div className="tile w" style={{ top: "8%", right: "10%", width: 28, height: 28 }} />
        <div className="tile" style={{ top: "48%", right: "12%", width: 72, height: 160 }} />
        <p className="quote">Sohbet et, görselini üret, reklamını yayınla. Hepsi tek yerde.</p>
      </div>
    </div>
  );
}
