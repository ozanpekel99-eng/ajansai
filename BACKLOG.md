# ajansAI — yapılacaklar listesi (gece geliştirme görevi buradan çalışır)

Kurallar:
- Gece görevi her çalışmada **en üstteki işaretlenmemiş** maddeyi alır, `gece/<kısa-ad>` dalında çalışır,
  testleri geçirir ve **main'e doğrudan göndermez**; pull request açar. Ozan onaylayınca birleştirilir.
- Bitirilen maddeyi `[x]` yapar ve PR bağlantısını yanına yazar (aynı PR içinde).
- Şifre, ödeme, Meta reklam yayını, mağaza gönderimi gibi işleri yapmaz; bunları "Ozan'a" bölümüne not eder.
- Bir madde tek gecede bitmeyecek kadar büyükse önce maddeyi alt adımlara böler, ilk adımı yapar.

## Sıradaki işler (öncelik sırasıyla)

- [ ] Backend+Web (yönetici): Sosyal medya yayın kuyruğu — `marketing/<hafta>/plan.json`'daki onaylı paylaşımları yöneticinin kayıtlı Meta bağlantısıyla Instagram @ajansai.tr hesabına planlı saatinde paylaşan Vercel Cron (Instagram Graph API: görsel, carousel, Reels; `instagram_content_publish` izni gerekir), web'de yöneticiye özel onay sayfası (her gönderi: onayla / düzenle / atla) ve paylaşım sonrası etkileşim özetinin günlük rapora eklenmesi. Meta reklamları (Ajans AI reklam hesabı act_1823149412206641, yalnızca Instagram yerleşimi, günlük 1.000 TL, hedef satın alma, piksel 1084755444379431) için günlük performans özeti ve öneri; bütçe/kampanya değişikliği yalnızca Ozan onayıyla
- [ ] Backend: Instagram DM otomatik yanıt — Meta webhook (`/api/meta/webhook`, mesaj olayları) ile @ajansai.tr'ye gelen DM'leri al, Claude ile ajansAI bilgileri (paketler, ücretsiz paket, nasıl kullanılır) üzerinden Türkçe cevap ver; emin olmadığı sorularda support@ajansai.tr'ye yönlendir; konuşmaları yönetici sayfasında listele. `instagram_manage_messages` izni (uygulama incelemesi) gelene kadar kapalı kalsın
- [x] Web: KVKK uyumlu çerez onay bandı — Meta Pikseli (`web/app/components/MetaPixel.tsx`) yalnızca kullanıcı 'Kabul et' derse yüklensin (`fbq('consent','revoke'/'grant')`); seçim localStorage'da saklansın; bant sade, mobilde ekranı kapatmasın; gizlilik sayfasına bağlantı — PR #6
- [ ] Mobil: Reklam ekranı — Meta bağlantı durumu (`/api/ads/meta/status`), reklam listesi (`/api/ads/meta/ads`), kütüphaneden görsel/video seçip Instagram reklamı oluşturma akışı (web'deki `Reklam.tsx` ile aynı uçlar; yerleşimler yalnızca Instagram)
  - [x] 1/3: Paket kilidi, Meta bağlantı durumu (bağlı değilse ajansai.tr'ye yönlendirme), "Reklamlarım" listesi (tarih aralığı, özet ve reklam bazında metrikler, dakikalık yenileme, Yayına al onaylı / Durdur, Meta'da aç, bağlantıyı kaldır) — PR #9 (https://github.com/ozanpekel99-eng/ajansai/pull/9)
  - [ ] 2/3: Uygulamadan Meta bağlama — backend'de `state`'ten kullanıcıyı bulan oturumsuz callback + `ajansai://` derin bağlantıyla uygulamaya dönüş (`expo-web-browser` `openAuthSessionAsync`)
  - [ ] 3/3: Yeni reklam akışı — kütüphaneden görsel/video seçimi, reklam hesabı/sayfa/Instagram seçimi, `/api/ads/meta/ad-copy` ile metin, hedef, bütçe, konum; yalnızca Instagram yerleşimleri; `/api/ads/meta/ads` POST
- [ ] Mobil: Google ile giriş ve Apple ile giriş (`expo-apple-authentication`; backend `/api/auth/google`, `/api/auth/apple`; Apple id_token audience'ına `tr.ajansai.app` paket kimliğini ekle — `backend/app/services/social_auth.py`)
- [x] Mobil: Sohbette video önerisi ve ücretsiz kullanıcı limit kartı (web `UpgradeCard` karşılığı; limit dolunca paketler gösterilsin) — [PR #11](https://github.com/ozanpekel99-eng/ajansai/pull/11)
  - [x] 1/2: iOS'ta Apple ile giriş — backend Apple audience'ı web Services ID + `tr.ajansai.app` (`APPLE_BUNDLE_ID`); giriş ekranında yerel "Apple ile devam et" butonu ([#10](https://github.com/ozanpekel99-eng/ajansai/pull/10))
  - [ ] 2/2: Google ile giriş (iOS + Android) — Google Cloud'da iOS/Android OAuth istemci kimlikleri (Ozan'a), backend Google audience listesine mobil istemci kimlikleri, giriş ekranına Google butonu
- [ ] Mobil: Sohbette video önerisi ve ücretsiz kullanıcı limit kartı (web `UpgradeCard` karşılığı; limit dolunca paketler gösterilsin)
- [ ] Mobil: Uygulama içi satın alma altyapısı — RevenueCat (`react-native-purchases`) ekranı ve backend webhook ucu (`/api/payments/revenuecat/webhook`: ürün kimliği → paket/ek kredi; idempotent; testli). Gerçek anahtarlar Ozan girene kadar kapalı kalsın
  - [x] 1/3 Backend: RevenueCat webhook ucu (ürün kimliği → paket/ek kredi, olay kimliğiyle tekrar korumalı, `REVENUECAT_WEBHOOK_AUTH` yoksa kapalı) — [PR #13](https://github.com/ozanpekel99-eng/ajansai/pull/13)
  - [ ] 2/3 Mobil: Paketler ekranında uygulama içi satın alma (`react-native-purchases`; `Purchases.logIn(<kullanıcı id>)`, teklifler, satın al / geri yükle; RevenueCat anahtarı yoksa ekran web'e yönlendirir). Ek kredi yalnızca ücretli paketi olana gösterilsin
  - [ ] 3/3 Backend: İade ve paket değişikliği — `CANCELLATION` (iade nedeniyle) olayında paketi kapat, `PRODUCT_CHANGE` / yükseltmeyi işle; yönetici sayfasında `store_events` listesi
- [ ] Mobil: Görsel düzenleme ve video sonuçlarında "Reklam ver" kısayolu
- [x] Backend: `/api/health/qa` raporuna son 24 saatteki üretim hata sayıları (video_tasks failed, görsel hataları) eklensin — PR #14 (https://github.com/ozanpekel99-eng/ajansai/pull/14)
  - [x] 1/2: Görsel (üretim/düzenleme), video ve kütüphane sonuçlarında "Reklam ver" düğmesi — paketi olmayana paket uyarısı, olana ajansai.tr Reklam sayfası web ile aynı biçimde açılır (`/araclar/reklam?medya=…&tur=gorsel|video&konsept=…`, `mobile/src/lib/adShortcut.ts`) — PR #17 (https://github.com/ozanpekel99-eng/ajansai/pull/17)
  - [ ] 2/2: Mobil reklam oluşturma akışı (Mobil Reklam 3/3) gelince düğme web yerine uygulamadaki Reklam ekranını açsın ve dosyayı yeni reklama eklesin
- [ ] Backend: `/api/health/qa` raporuna son 24 saatteki üretim hata sayıları (video_tasks failed, görsel hataları) eklensin
- [ ] Web: Kütüphane ve görsel/video sonuçlarında "Reklam ver" kısayolu (mobil ile tutarlı)
- [ ] Backend (kalite, 05.11 denetimi — 26.10'dan sonra 2. kez; PR #22 ve PR #7'deki küçük madde): Referans fotoğrafı olmayan ürünlerde kontrol panelinde anlamsız sahte yazı ve sahte logo — beyaz eşya görselinde program etiketleri okunamaz harf yığını, kurutma makinesinde logo benzeri leke; otomatik denetim "sorunsuz" dedi. İki adım:
  - [x] 1/2 İstem ve denetim kuralları: `AD_DIRECTOR_SYSTEM` ve `IMAGE_SYSTEM`'e "fotoğrafsız ürün: temiz, markasız; panel/ekranda yalnızca basit ikon, düğme ve boş koyu ekran — küçük yazı, model adı, logo yok" kuralı; fotoğraf yoksa istem yazarına bu açıkça söyleniyor; `QA_SYSTEM` 6. madde: panel/ekrandaki sahte etiketler ve sahte logolar kusur (gece/sahte-panel-yazisi)
  - [ ] 2/2 `media_qa._data_url` 1024 px JPEG küçültmesi küçük yazıyı görünmez kılıyor: denetime daha yüksek çözünürlük ve ürün/yazı bölgelerinin büyütülmüş kırpımları gönderilsin (29.10'daki Türkçe İ yanlış alarm maddesiyle birlikte yapılabilir)

## Kalite denetiminden (PR #12'de önerilen madde)

- [ ] Backend (kalite, 29.10 QA raporu): Görsel denetimi Türkçe büyük İ için yanlış alarm veriyor — "PÜRÜZSÜZ CİLT" doğru yazılı olduğu hâlde denetim "CILT" diye kusur bildirdi, görsel boşuna yeniden üretildi (~2 kat maliyet). Alt adımlar:
  - [x] 1/3: Denetime giden görsel 1024 px JPEG yerine uzun kenarı 1568 px'e kadar kayıpsız PNG (çok büyükse JPEG q95); `QA_SYSTEM` 1. maddeye "İ/ı, Ş, Ğ, Ç, Ö, Ü isteğe uygunsa doğrudur; nokta/çengel kusurunu yalnızca kesinse bildir" kuralı (gece/qa-turkce-harf)
  - [ ] 2/3: Yazı bölgelerinin büyütülmüş kırpımlarını denetime ekle (PR #23'teki panel yazısı 2/2 adımıyla ortak)
  - [ ] 3/3: Kusur listesinde yalnızca Türkçe karakter şikâyeti varsa yeniden üretmeden önce kırpımla ikinci doğrulama yap; doğrulanmayan şikâyet yeniden üretim istemine girmesin
- [x] Backend (kalite, 05.11 ve 09.11 denetimleri): Aynı yazının görselde iki kez çıkması — kafede "YENİ SEZON" hem üst kurdelede hem fiyat kutusunda, beyaz eşyada "İKİLİ ALIMDA FIRSAT" başlığının altında yine "İKİLİ ALIMDA". `AD_DIRECTOR_SYSTEM`'e "her ifade afişte yalnızca bir kez; başlık teklif satırının kelimelerini tekrarlamasın" kuralı, `QA_SYSTEM`'e 7. kusur maddesi "same phrase rendered twice" (PR #22 ve #28'deki ilgili maddelerin karşılığı) — PR: gece/yazi-tekrari

## Kalite denetiminden (PR #12'de önerilen madde)

- [ ] Backend (kalite, 29.10): `media_qa.generate_checked` yeniden üretilen görseli denetlemeden döndürüyordu. Alt adımlar:
  - [x] 1/2: İkinci görsel de denetleniyor, kusuru daha az olan seçiliyor (eşitse ilki) — PR #26
  - [ ] 2/2: Yeniden üretim istemine yalnızca doğrulanmış kusurlar eklensin (PR #24'teki Türkçe İ maddesinin 3/3 adımıyla birlikte; yanlış alarmlar isteme "CILT yazma" gibi gereksiz talimat sokmasın)
- [x] Backend (kalite, 09.11 ve 12.11 denetimleri): Paket "+" rozeti kırmızı daire içinde beyaz haç (ilk yardım işareti) gibi çiziliyordu; `AD_DIRECTOR_SYSTEM`'de rozet "altın ya da marka renginde artı işareti, asla kırmızı daire üstünde beyaz haç" olarak tarif edildi. Örnek başlık "EVİNİZİN İKİ GÜÇLÜSÜ" teklif satırıyla kelime paylaştığı için ("İKİLİ" üç kez) teklifle kelime paylaşmayan bir örnekle değiştirildi ve "başlık teklif satırıyla kelime paylaşmasın" kuralı eklendi — PR: gece/arti-rozeti

## Kalite denetiminden (PR #7 / #12 / #18'de önerilen maddeler)

- [x] Backend (kalite, 26.10): `media_planner.VIDEO_SYSTEM`'e kampanya görseli kuralı — başlangıç karesindeki yazı/fiyat/rozet/bant video boyunca sabit kalsın, yalnızca arka plan öğeleri hareket etsin; yedek istemde başlangıç karesi varsa "no text" yerine "keep all existing text exactly unchanged" — PR (bu dal: gece/video-yazi-sabit)

## Kalite denetiminden (PR #7 / #18'de önerilen maddeler)

- [x] Backend (kalite, 02.11): QA videosu gerçek akıştaki açılış karesi genişletmesini atlıyordu (siyah bant). `_fit_frame` `app/services/video_frame.py`'ye taşındı; `/video` ve `qa_run` aynı fonksiyonu kullanıyor, QA raporuna `video.frame_url` / `video.frame_fitted` eklendi — PR #19

## Kalite denetiminden (PR #12'de önerilen madde)

- [x] Backend (kalite, 29.10): `/api/health/qa` her görsel için ilk denemenin kusurlarını (`first_problems`), yeniden üretim yapılıp yapılmadığını (`retried`, başarısızsa `retry_error`) ve son görselin denetimini (`problems`) ayrı alanlarda veriyor; kalite e-postasında "İlk denemede N kusur (yeniden üretildi)" satırı — PR #34 (https://github.com/ozanpekel99-eng/ajansai/pull/34)
- [ ] Backend (kalite, 09.11 denetimi — PR #28'deki madde): Video son-kare güvencesi — Veo çıktısının kapanışında yazılar bozuluyorsa ek üretim maliyeti olmadan son sağlam kareyi tutarak süreyi koru
  - [x] 1/3 `video_endguard.guard`: ffmpeg ile kareleri çıkar, son 0,6 sn'yi gövdedeki olağan değişimle karşılaştır; bozulmada son sağlam karede kes, `tpad=stop_mode=clone` ile süreyi koru; kullanıcı videolarında (`_store_video`) ve `/api/health/qa` raporunda (`video.end_guard`) devrede, `VIDEO_END_GUARD=0` ile kapatılabilir (PR: gece/video-son-kare)
  - [ ] 2/3 Karşılaştırmayı yazı bölgelerine odakla: başlangıç karesindeki yazı kutularını (görme modeli ya da kenar yoğunluğu) bir kez bul, yalnızca o bölgelerde fark ölç (ışık/konfeti kaynaklı yanlış alarmı azaltır)
  - [ ] 3/3 Gerçek Veo çıktılarıyla eşik ayarı: son 2 haftanın QA videolarında `end_guard` ölçümlerini (normal / end_max) rapora dök, `RATIO`/`MIN_DIFF` değerlerini buna göre güncelle

## Kalite denetiminden (PR #7 / #12 / #18'de önerilen maddeler)

- [ ] Backend (kalite, 26.10 + 02.11): Video otomatik denetimi `media_qa.check_video` — alt adımlar:
  - [x] 1/3: Siyah bant (letterbox) tespiti — ilk karenin üst/alt şeritleri (1080x1920'de 200 px) ortalama parlaklık <10 ise kusur; `cropdetect` kullanılmadı (konfetide yanılıyor). Yalnızca servis fonksiyonu + testler, henüz hiçbir akışa bağlı değil — PR (bu dal: gece/video-denetimi)
  - [ ] 2/3: ffmpeg ile ~8 kare (ilk 2 sn'den sık) çıkarıp başlangıç karesiyle birlikte görme modeline ver; yazı bozulması/kaybolması, ürün/insan bozulması
  - [ ] 3/3: `/api/health/qa` raporuna `video.ok` / `video.problems`; üretimde kusurda bir kez yeniden üretim (PR #14 ve #19 birleştikten sonra, health.py çakışmasın diye)
  - Not: mobil reklam oluşturma akışına bağlı (PR #9, Mobil Reklam 1/3 — oluşturma 2/3 adımında). O birleşince web ile aynı biçimi kullan: `/araclar/reklam?medya=<https url>&tur=gorsel|video&konsept=<açıklama>` (`web/app/lib/adShortcut.ts`)
- [ ] Backend: `/api/health/qa` raporuna son 24 saatteki üretim hata sayıları (video_tasks failed, görsel hataları) eklensin
- [x] Web: Kütüphane ve görsel/video sonuçlarında "Reklam ver" kısayolu (mobil ile tutarlı) — PR #16

## Ozan'a (insan gerektiren işler)

- Apple Developer hesabı (yıllık $99) → iOS TestFlight
- Google Play Console ($25) → Play iç test
- RevenueCat hesabı ve mağaza ürünleri (ürün kimlikleri: `ajansai_baslangic_aylik`, `ajansai_pro_yillik`, `ajansai_kredi_100` … — tam liste `backend/app/services/revenuecat.py`; webhook: `https://<backend>/api/payments/revenuecat/webhook`, Authorization değeri Vercel'de `REVENUECAT_WEBHOOK_AUTH`)
- Meta işletme doğrulaması sonucu → uygulama incelemesi gönderimi (`instagram_content_publish`, `instagram_manage_messages`)

## Kalite denetiminden (PR #12'de önerilen madde)

- [x] Backend (kalite, 29.10): `media_planner` istem kuralına "başlıkta tek tip büyük/küçük harf (tümü büyük ya da her kelimenin baş harfi büyük); small-caps veya karışık harf boyu yok" eklendi — hem `AD_DIRECTOR_SYSTEM` hem `IMAGE_SYSTEM` (mobilya görselinde başlık "Evinize Yeni bir Hava" çıkmıştı) — gece/baslik-harf-tutarliligi
