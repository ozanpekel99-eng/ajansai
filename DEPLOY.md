# ajansAI — Canlıya alma rehberi

> **Şu anki canlı kurulum (Vercel):** Web `ajansai` projesinde, backend `ajansai-api` projesinde (kök klasör
> `backend`), veritabanı Vercel Marketplace üzerinden Neon Postgres. Yapay zeka çağrıları API key gerektirmeyen
> **Vercel AI Gateway** üzerinden Claude'a gider (`AI_GATEWAY_MODEL`, varsayılan `anthropic/claude-sonnet-5`).
> OmniRoute eklenince `OMNIROUTE_BASE_URL` / `OMNIROUTE_API_KEY` tanımlamak yeterli; AI Gateway otomatik yedek olur.
> Aşağıdaki Railway adımları OmniRoute'u ayrı sunucuya kurmak için geçerli.

Kurulacak yapı:

```
                ┌──────────────── Railway projesi ────────────────┐
 Vercel (web) ──┼─► backend (FastAPI) ──► OmniRoute ──► Claude      │
 Expo (mobil) ──┘        │                                         │
                         └──► Postgres                             │
                └──────────────────────────────────────────────────┘
 iyzico ──(ödeme sonucu)──► backend
```

Sıra önemli: **1) Postgres → 2) OmniRoute → 3) Backend → 4) Web → 5) iyzico.**
Her adımın sonunda bir kontrol var. Kontrol geçmeden bir sonrakine geçme.

Gizli değerleri (`JWT_SECRET` gibi) senin için rastgele ürettim. Değerler masaüstündeki
**ajansai-gizli-degerler.txt** dosyasında. Tablolarda "dosyadan" yazan yerlere
o dosyadaki ilgili satırı kopyala. Kurulum bitince dosyayı sil.

---

## 1. Postgres

1. Railway → **New Project → Deploy PostgreSQL**.
2. Hepsi bu. `DATABASE_URL` değişkenini 3. adımda backend'e bağlayacağız.

---

## 2. OmniRoute (AI ağ geçidi)

1. Aynı projede **New → Docker Image** seç ve imaj olarak `diegosouzapw/omniroute:3.8.51` yaz.
2. **Settings → Volumes → Add Volume**. Mount path: `/app/data`.
   Bu ayar olmazsa her deploy'da OmniRoute'un ayarları ve key'leri silinir.
3. **Variables** sekmesine şunları ekle:

| Değişken | Değer |
|---|---|
| `PORT` | `20128` |
| `DATA_DIR` | `/app/data` |
| `REQUIRE_API_KEY` | `true` ← **zorunlu**. Yoksa herkes senin Claude key'inle istek atabilir. |
| `INITIAL_PASSWORD` | Kendi belirleyeceğin güçlü bir dashboard şifresi |
| `JWT_SECRET` | dosyadan: `OMNIROUTE_JWT_SECRET` |
| `API_KEY_SECRET` | dosyadan: `OMNIROUTE_API_KEY_SECRET` |
| `STORAGE_ENCRYPTION_KEY` | dosyadan: `OMNIROUTE_STORAGE_ENCRYPTION_KEY` |
| `OMNIROUTE_WS_BRIDGE_SECRET` | dosyadan: `OMNIROUTE_WS_BRIDGE_SECRET` |
| `AUTH_COOKIE_SECURE` | `true` |

4. **Settings → Networking → Generate Domain**. Port olarak 20128 seç.
   Çıkan adresi `NEXT_PUBLIC_BASE_URL` değişkeni olarak da ekle, örneğin `https://omniroute-production.up.railway.app`.
5. Railway planında servisin en az **2 GB RAM** kullanabildiğinden emin ol.
6. Dashboard'a gir (`https://<omniroute-adresi>`) ve `INITIAL_PASSWORD` ile giriş yap:
   - **Sağlayıcılar → Anthropic → Bağlantı Ekle**: Claude API key'ini ekle.
   - İstersen yedek olarak **Gemini** gibi ikinci bir sağlayıcı da ekle.
   - **Uç Noktalar → Kayıtlı Anahtarlar → yeni anahtar**: adını `ajansai-backend` koy.
     Çıkan anahtarı kopyala, 3. adımda lazım. Anahtar bir daha gösterilmez.
   - ⚠️ **Genel Sistem İstemi'ni ve Omni Skills'i bu sunucuda AÇMA.** ajansAI modelden
     katı JSON bekliyor. Araya giren talimatlar ve araçlar yanıtı bozar.

**Kontrol:** Kendi bilgisayarında şunu çalıştır (`<KEY>` yerine az önce aldığın anahtarı yaz):

```
curl https://<omniroute-adresi>/v1/chat/completions -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" -d "{\"model\":\"anthropic/claude-sonnet-5\",\"messages\":[{\"role\":\"user\",\"content\":\"merhaba\"}]}"
```

Cevap gelmeli. Anahtarsız denediğinde ise 401 hatası almalısın.

---

## 3. Backend (FastAPI)

1. Kodu GitHub'a gönder. Railway'de **New → GitHub Repo** ile depoyu seç.
2. **Settings → Root Directory**: `backend`.
   `backend/railway.json` dosyası başlatma komutunu ve sağlık kontrolünü kendisi ayarlar.
3. **Settings → Networking → Generate Domain**. Çıkan adres örneğin `https://ajansai-api.up.railway.app` olur.
4. **Variables** sekmesine şunları ekle:

| Değişken | Değer |
|---|---|
| `ENVIRONMENT` | `production` |
| `JWT_SECRET` | dosyadan: `BACKEND_JWT_SECRET` (OmniRoute'unkinden farklı) |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` |
| `PUBLIC_API_URL` | Backend'in kendi adresi, örn. `https://ajansai-api.up.railway.app` |
| `WEB_URL` | Vercel adresi (4. adımdan sonra güncelle), örn. `https://ajansai.vercel.app` |
| `ALLOWED_ORIGINS` | `WEB_URL` ile aynı. Birden fazla adres varsa virgülle ayır. |
| `OMNIROUTE_BASE_URL` | `https://<omniroute-adresi>/v1` |
| `OMNIROUTE_API_KEY` | 2. adımda oluşturduğun anahtar |
| `OMNIROUTE_MODEL` | `anthropic/claude-sonnet-5`. Daha ucuz bir model ya da OmniRoute'taki bir combo adı da olabilir. |
| `ANTHROPIC_API_KEY` | Claude key'in. **Yedek** olarak kullanılır: OmniRoute çökerse uygulama doğrudan Claude'la çalışmaya devam eder. |
| `BLOB_READ_WRITE_TOKEN` | Vercel → Storage → Blob deposu projeye bağlanınca otomatik gelir (görsel/video saklama) |
| `META_APP_ID` / `META_APP_SECRET` | (Meta App Review onayından sonra) |
| `META_REDIRECT_URI` | `<WEB_URL>/ads/callback` |
| `IYZICO_*` | 5. adımda |

**Kontrol:** Tarayıcıda `https://<backend-adresi>/health` adresini aç. Şu çıkmalı:
`"ai":"omniroute"`, `"ai_fallback":true`, `"database":"postgres"`.

---

## 4. Web (Vercel)

1. Vercel → **Add New → Project**, aynı GitHub deposunu seç.
2. **Root Directory**: `web`.
3. **Environment Variables**: `NEXT_PUBLIC_API_URL` = backend adresi (sonunda `/` olmadan).
4. Deploy et. Çıkan Vercel adresini backend'deki `WEB_URL`, `ALLOWED_ORIGINS` ve
   `META_REDIRECT_URI` değişkenlerine yaz. Railway backend'i kendiliğinden yeniden başlatır.

**Kontrol:** Siteye gir, kayıt ol ve bir fikir üret. Fikirler gelmeli.
Ardından OmniRoute dashboard'unda **İstek Günlükleri** ekranında bu isteği görmelisin.

---

## 5. iyzico

1. Test için https://sandbox-merchant.iyzipay.com adresinden sandbox hesabı aç
   ve **Ayarlar → API Anahtarları** ekranından test anahtarlarını al.
2. Backend değişkenleri:
   - `IYZICO_API_KEY`, `IYZICO_SECRET_KEY`: sandbox anahtarları
   - `IYZICO_BASE_URL`: `https://sandbox-api.iyzipay.com`
3. Sitede **Paketler → Pro → iyzico ile öde** adımlarını izle. Test kartı: `5528790000000008`,
   son kullanma tarihi gelecekte herhangi bir tarih, CVC `123`.
   Ödeme bitince "Ödeme alındı" sayfası çıkmalı ve paketin Pro'ya geçmeli.
4. Canlıya geçmek için iyzico'dan gerçek üye işyeri onayı al. Ardından anahtarları canlı anahtarlarla,
   `IYZICO_BASE_URL` değerini de `https://api.iyzipay.com` ile değiştir.

---

## 6. Mobil (Expo)

`mobile/config.js` dosyasında `API_URL` değerini backend adresi, `WEB_URL` değerini Vercel adresi yap.
Ardından `npm install` ve `npx expo start` komutlarını çalıştır. Mobilde paket satın alma web sitesine yönlendirir.

---

## Sorun giderme

| Belirti | Bakılacak yer |
|---|---|
| Web'de "Sunucuya ulaşılamadı" | `NEXT_PUBLIC_API_URL` doğru mu? Backend'deki `ALLOWED_ORIGINS` içinde Vercel adresi var mı? |
| `/health` → `"ai":"anthropic"` | `OMNIROUTE_BASE_URL` tanımlı değil |
| Fikirler geliyor ama OmniRoute günlüğünde görünmüyor | OmniRoute hata veriyor ve sistem Claude'a düşüyor. Railway backend loglarında `OmniRoute başarısız` satırını ara. |
| Ödeme sonrası paket açılmadı | Backend loglarında `iyzico` satırlarına bak. `PUBLIC_API_URL` doğru mu? |
| Her deploy'da kullanıcılar siliniyor | `DATABASE_URL` Postgres'e bağlı değil (`/health` → `"database":"sqlite"`) |

## Veo videoları: Google Cloud Vertex AI (önerilen)

AI Gateway ~16 MiB'tan büyük Veo videolarını geri vermiyor. Vertex tanımlıysa Veo doğrudan oradan,
istenen çözünürlükte çağrılır; Vertex başlamazsa AI Gateway (720p üret + sunucuda büyüt), o da olmazsa Kling.

| Değişken | Açıklama |
|---|---|
| `GOOGLE_VERTEX_CREDENTIALS` | Servis hesabı anahtarı (JSON, düz ya da base64). Rol: **Vertex AI User** |
| `VERTEX_PROJECT` | İsteğe bağlı; boşsa anahtardaki `project_id` |
| `VERTEX_LOCATION` | Varsayılan `us-central1` |
| `VERTEX_VIDEO_BUCKET` | İsteğe bağlı; videolar `gs://<bucket>/video/` altına yazılır (servis hesabına bu bucket'ta Storage Object Admin) |
| `VERTEX_VIDEO` | `0` yapılırsa Vertex kullanılmaz |
