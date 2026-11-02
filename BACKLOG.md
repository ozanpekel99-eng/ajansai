# ajansAI — yapılacaklar listesi (gece geliştirme görevi buradan çalışır)

Kurallar:
- Gece görevi her çalışmada **en üstteki işaretlenmemiş** maddeyi alır, `gece/<kısa-ad>` dalında çalışır,
  testleri geçirir ve **main'e doğrudan göndermez**; pull request açar. Ozan onaylayınca birleştirilir.
- Bitirilen maddeyi `[x]` yapar ve PR bağlantısını yanına yazar (aynı PR içinde).
- Şifre, ödeme, Meta reklam yayını, mağaza gönderimi gibi işleri yapmaz; bunları "Ozan'a" bölümüne not eder.
- Bir madde tek gecede bitmeyecek kadar büyükse önce maddeyi alt adımlara böler, ilk adımı yapar.

## Sıradaki işler (öncelik sırasıyla)

- [ ] Backend (kalite, 02.11 denetimi — 26.10'dan sonra 2. kez): QA videosunda siyah bant tekrarladı — 4:5 mobilya görselinden 1080x1920 video üretildi, içerik ortada 1080x1350, üstte/altta ~285 px siyah bant (altın kurdeleler bandın içine sarkıyor). Sebep: `health.qa_run` kaynak görseli `gateway_media.start_video`'ya doğrudan veriyor; üretimdeki `content._fit_frame` (9:16'ya genişletme) adımı atlanıyor, yani QA gerçek akışı test etmiyor. Düzeltme: `_fit_frame`'i `content.py`'den bir servise (ör. `media_planner` yanına `video_frame.py`) taşı, hem `/video` hem `qa_run` aynı fonksiyonu çağırsın; `qa_run` raporuna `video.frame_url` (genişletilmiş açılış karesi) eklensin. (PR #7'deki ilk madde bununla birleştirilebilir)
- [ ] Backend (kalite): `_fit_frame` genişletmesi tüm afişi yeniden çizdiriyor (GPT Image düzenlemesi), ama sonucu denetlemiyor — yazı/fiyat bozulursa video bozuk kareyle başlar. Genişletilmiş kareyi `media_qa.check_image(data, request)` ile denetle; kusur varsa bir kez yeniden dene, yine kusurluysa orijinal kareyi değil, videonun oranını kaynak orana en yakın desteklenen orana çek ya da kullanıcıya oran uyarısı göster. Genişletme başarısız olursa (`except` dalı) şu an sessizce orijinal URL dönüyor → üretimde de siyah bant; bu durum loglanıp kullanıcıya not olarak dönsün
- [ ] Backend (kalite): `media_qa.check_video` (PR #7'deki madde) yazılırken ilk kontrol siyah bant olsun: `ffmpeg -vf cropdetect` konfeti/kurdele yüzünden yanılıyor (bu videoda 1080x1634 buldu); bunun yerine ilk karede üst/alt 200 px şeritlerin ortalama parlaklığı <10 ise "letterbox" kusuru say. Bugünkü rapor bu kusura rağmen `status: completed` gösterdi; video için `ok`/`problems` alanı hâlâ yok
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

- Apple Developer hesabı (yıllık $99) → iOS TestFlight
- Google Play Console ($25) → Play iç test
- RevenueCat hesabı ve mağaza ürünleri
- Meta işletme doğrulaması sonucu → uygulama incelemesi gönderimi (`instagram_content_publish`, `instagram_manage_messages`)
