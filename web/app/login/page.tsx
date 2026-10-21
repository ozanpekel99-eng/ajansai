"use client";

import { FormEvent, useState } from "react";

import { api, setToken } from "../lib/api";

export default function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
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
    <div className="page">
      <header className="header">
        <img src="/logo.png" alt="ajansAI" className="logo" />
      </header>

      <div className="auth-wrap">
        <section className="hero">
          <h1>{mode === "login" ? "Tekrar hoş geldin." : "Hesabını oluştur."}</h1>
          <p>
            {mode === "login"
              ? "İçerik fikirlerine ve paketine ulaşmak için giriş yap."
              : "Ücretsiz deneme ile başla, ayda 10 içerik fikri senden."}
          </p>
        </section>

        <form className="form-card" onSubmit={submit}>
          {mode === "register" && (
            <div className="field">
              <label>Ad soyad</label>
              <input value={form.name} onChange={(e) => update("name", e.target.value)} autoComplete="name" />
            </div>
          )}
          <div className="field">
            <label>E-posta</label>
            <input
              required
              type="email"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label>Şifre</label>
            <input
              required
              type="password"
              minLength={mode === "register" ? 8 : undefined}
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder={mode === "register" ? "En az 8 karakter" : ""}
            />
          </div>
          <div className="submit-row">
            <button className="primary" type="submit" disabled={loading}>
              {loading ? "Bekle…" : mode === "login" ? "Giriş yap" : "Hesap oluştur"}
            </button>
            {error && <span className="error-text">{error}</span>}
          </div>
        </form>

        <div className="switch-link">
          {mode === "login" ? "Hesabın yok mu? " : "Zaten hesabın var mı? "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "Kayıt ol" : "Giriş yap"}
          </button>
        </div>
      </div>
    </div>
  );
}
