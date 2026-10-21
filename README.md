# ajansAI — KOBİ'ler için İçerik ve Reklam Asistanı

```
backend/   → FastAPI (giriş, içerik fikri, görsel, video, Meta Ads, iyzico ödeme)
web/       → Next.js web arayüzü
mobile/    → Expo (React Native) mobil uygulama, aynı backend'i kullanır
DEPLOY.md  → Railway + Vercel + iyzico canlıya alma rehberi (adım adım)
```

## Durum

| Özellik | Durum | Not |
|---|---|---|
| Kayıt / giriş | ✅ | E-posta + şifre, JWT. Tüm uç noktalar giriş istiyor. |
| İçerik fikri üretimi | ✅ | OmniRoute üzerinden çalışır. OmniRoute çökerse otomatik olarak doğrudan Claude'a düşer. |
| Paketler ve kota | ✅ | Kota atomik olarak düşülür; aynı anda gelen istekler kotayı aşamaz. Sağlayıcı hatasında kota iade edilir. |
| iyzico ödeme | ✅ (sandbox anahtarıyla test edilmeli) | Paket yalnızca iyzico'dan doğrulanan ödemeyle açılır, 30 gün geçerlidir. |
| Veritabanı | ✅ | Railway'de Postgres, yerelde SQLite. Aynı kod ikisinde de çalışır. |
| Görsel üretimi | ✅ | Vercel AI Gateway (Seedream 5.0 Pro), 4 kredi |
| Video üretimi | ✅ | Vercel AI Gateway (Seedance 1.5 Pro, 720p dikey), 5 sn 12 / 10 sn 24 kredi |
| Meta Ads | ⚙️ Kod hazır | Hesap bağlama, reklam hesapları, PAUSED kampanya taslağı. **Meta App Review onayı şart.** |
| Mobil | ✅ Temel akış | Giriş, fikir, video. Paket satın alma web'e yönlendirir. |

## Paketler

Tek doğruluk kaynağı: `backend/app/services/plans.py`.

| Paket | Fiyat (30 gün) | Video | Görsel | Fikir | Reklam |
|---|---|---|---|---|---|
| Deneme (ücretsiz, kayıtta otomatik) | ₺0 | 0 | 0 | 10/ay | Yok |
| Başlangıç | ₺499 | 10 | 30 | Sınırsız | Yok |
| Pro | ₺1.249 | 30 | 60 | Sınırsız | Var |
| Ajans | ₺1.999 | 45 | 100 | Sınırsız | Var |

Ücretli paket bitince kullanıcı Deneme'ye döner. Aynı paket süresi bitmeden
yenilenirse kalan günler korunur.

## Yapay zeka katmanı (OmniRoute)

Bütün metin üretimi `backend/app/services/llm_service.py` dosyasından geçer:

1. `OMNIROUTE_BASE_URL` tanımlıysa istek OmniRoute'a gider (OpenAI uyumlu `/chat/completions`).
   Model seçimi, yedek sağlayıcılar ve maliyet takibi OmniRoute panelinden yönetilir;
   model değiştirmek için kod değil yalnızca `OMNIROUTE_MODEL` değişir.
2. OmniRoute yoksa ya da hata verirse, `ANTHROPIC_API_KEY` tanımlıysa doğrudan Claude'a gider.

`/health` uç noktası hangi yolun aktif olduğunu gösterir.

## Yerelde çalıştırma

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env              # en azından ANTHROPIC_API_KEY veya OMNIROUTE_* doldur
uvicorn app.main:app --reload --port 8000
pytest                            # 25 test

# Web
cd web
npm install
npm run dev                       # http://localhost:3000

# Mobil
cd mobile
npm install
npx expo start
```

API dokümantasyonu (yalnızca geliştirme ortamında): http://localhost:8000/docs

## Sırada ne var?

1. **iyzico abonelik (otomatik yenileme):** Şu an her ay elle yeniden ödeniyor. iyzico Abonelik API'si ile otomatik tahsilat eklenebilir.
2. **Şifremi unuttum ve e-posta doğrulama:** Bir e-posta servisi (ör. Resend) gerekiyor.
3. **Fatura:** iyzico ödemesinden sonra e-arşiv faturası (ör. Paraşüt entegrasyonu).
4. **Google Ads entegrasyonu:** Developer Token başvurusu gerekiyor.
5. **İçerik takvimi ve otomatik paylaşım.**
