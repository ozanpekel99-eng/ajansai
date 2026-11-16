# ajansAI — yapılacaklar listesi (gece geliştirme görevi buradan çalışır)

Kurallar:
- Gece görevi her çalışmada **en üstteki işaretlenmemiş** maddeyi alır, `gece/<kısa-ad>` dalında çalışır,
  testleri geçirir ve **main'e doğrudan göndermez**; pull request açar. Ozan onaylayınca birleştirilir.
- Bitirilen maddeyi `[x]` yapar ve PR bağlantısını yanına yazar (aynı PR içinde).
- Şifre, ödeme, Meta reklam yayını, mağaza gönderimi gibi işleri yapmaz; bunları "Ozan'a" bölümüne not eder.
- Bir madde tek gecede bitmeyecek kadar büyükse önce maddeyi alt adımlara böler, ilk adımı yapar.

## Sıradaki işler (öncelik sırasıyla)

- [ ] Backend (kalite 16.11): Görsel istem yazarı ve denetimde "mockup çerçeve" kusuru — güzellik merkezi QA görseli afişin kendisi değil, pembe zemin üzerinde gölgeli bir poster mockup'ı olarak üretildi (kenarlarda ~%10 boşluk; Instagram'da küçük ve amatör görünüyor), otomatik denetim yakalamadı. `media_planner.py` `AD_DIRECTOR_SYSTEM` içindeki "Always:" satırına ekle: "The poster IS the whole image: full-bleed, edge to edge. Never render it as a mockup (a printed poster/card/frame on a background, a border or margin around the design, a drop shadow under it)." `media_qa.py` `QA_SYSTEM`'e 7. madde ekle: "7. The design is shown as a mockup — a poster/card/frame placed on a background with a visible border, margin or drop shadow — instead of filling the whole image." (Bu kusur stil değil, nesnel; 'Ignore style' kuralından önce yazılsın.) Test: `check_image` için sahte LLM yanıtıyla mockup kusuru dönünce yeniden üretimin tetiklendiği birim testi
- [ ] Backend (kalite 16.11): Video hata mesajında yedek modelin hatası kayboluyor — `gateway_media.start_video` `f"{model}: {e} | yedek: {e2}"` birleştiriyor, `health.py` bunu `[:300]` ile kestiği için yedeğin (Kling) neden düştüğü raporda görünmüyor ("yedek: AI " ile bitiyor). Ana ve yedek hatayı ayrı alanlarda sakla (`error`, `fallback_error`, her biri en fazla 300 karakter) veya ana hatayı 150 karakterle kısalt; AI Gateway 402/`insufficient_funds` hatasında rapora ve e-postaya açık "AI Gateway bakiyesi yetersiz — video üretimi durdu" satırı ekle
- [ ] Backend+Web (yönetici): Sosyal medya yayın kuyruğu — `marketing/<hafta>/plan.json`'daki onaylı paylaşımları yöneticinin kayıtlı Meta bağlantısıyla Instagram @ajansai.tr hesabına planlı saatinde paylaşan Vercel Cron (Instagram Graph API: görsel, carousel, Reels; `instagram_content_publish` izni gerekir), web'de yöneticiye özel onay sayfası (her gönderi: onayla / düzenle / atla) ve paylaşım sonrası etkileşim özetinin günlük rapora eklenmesi. Meta reklamları (Ajans AI reklam hesabı act_1823149412206641, yalnızca Instagram yerleşimi, günlük 1.000 TL, hedef satın alma, piksel 1084755444379431) için günlük performans özeti ve öneri; bütçe/kampanya değişikliği yalnızca Ozan onayıyla
- [ ] Backend: Instagram DM otomatik yanıt — Meta webhook (`/api/meta/webhook`, mesaj olayları) ile @ajansai.tr'ye gelen DM'leri al, Claude ile ajansAI bilgileri (paketler, ücretsiz paket, nasıl kullanılır) üzerinden Türkçe cevap ver; emin olmadığı sorularda support@ajansai.tr'ye yönlendir; konuşmaları yönetici sayfasında listele. `instagram_manage_messages` izni (uygulama incelemesi) gelene kadar kapalı kalsın
- [ ] Web: KVKK uyumlu çerez onay bandı — Meta Pikseli (`web/app/components/MetaPixel.tsx`) yalnızca kullanıcı 'Kabul et' derse yüklensin (`fbq('consent','revoke'/'grant')`); seçim localStorage'da saklansın; bant sade, mobilde ekranı kapatmasın; gizlilik sayfasına bağlantı
- [ ] Mobil: Reklam ekranı — Meta bağlantı durumu (`/api/ads/meta/status`), reklam listesi (`/api/ads/meta/ads`), kütüphaneden görsel/video seçip Instagram reklamı oluşturma akışı (web'deki `Reklam.tsx` ile aynı uçlar; yerleşimler yalnızca Instagram)
- [ ] Mobil: Google ile giriş ve Apple ile giriş (`expo-apple-authentication`; backend `/api/auth/google`, `/api/auth/apple`; Apple id_token audience'ına `tr.ajansai.app` paket kimliğini ekle — `backend/app/services/social_auth.py`)
- [ ] Mobil: Sohbette video önerisi ve ücretsiz kullanıcı limit kartı (web `UpgradeCard` karşılığı; limit dolunca paketler gösterilsin)
- [ ] Mobil: Uygulama içi satın alma altyapısı — RevenueCat (`react-native-purchases`) ekranı ve backend webhook ucu (`/api/payments/revenuecat/webhook`: ürün kimliği → paket/ek kredi; idempotent; testli). Gerçek anahtarlar Ozan girene kadar kapalı kalsın
- [ ] Mobil: Görsel düzenleme ve video sonuçlarında "Reklam ver" kısayolu
- [ ] Backend: `/api/health/qa` raporuna son 24 saatteki üretim hata sayıları (video_tasks failed, görsel hataları) eklensin
- [ ] Web: Kütüphane ve görsel/video sonuçlarında "Reklam ver" kısayolu (mobil ile tutarlı)

## Ozan'a (insan gerektiren işler)

- **Acil (16.11):** Vercel AI Gateway bakiyesi $10'un altında — Veo video üretimi 402 `insufficient_funds` ile duruyor (yedek model de çalışmadı). Bakiye yükle (Vercel → AI → Top up)
- Apple Developer hesabı (yıllık $99) → iOS TestFlight
- Google Play Console ($25) → Play iç test
- RevenueCat hesabı ve mağaza ürünleri
- Meta işletme doğrulaması sonucu → uygulama incelemesi gönderimi (`instagram_content_publish`, `instagram_manage_messages`)
