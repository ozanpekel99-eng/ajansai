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
- [ ] Web: KVKK uyumlu çerez onay bandı — Meta Pikseli (`web/app/components/MetaPixel.tsx`) yalnızca kullanıcı 'Kabul et' derse yüklensin (`fbq('consent','revoke'/'grant')`); seçim localStorage'da saklansın; bant sade, mobilde ekranı kapatmasın; gizlilik sayfasına bağlantı
- [ ] Mobil: Reklam ekranı — Meta bağlantı durumu (`/api/ads/meta/status`), reklam listesi (`/api/ads/meta/ads`), kütüphaneden görsel/video seçip Instagram reklamı oluşturma akışı (web'deki `Reklam.tsx` ile aynı uçlar; yerleşimler yalnızca Instagram)
- [ ] Mobil: Google ile giriş ve Apple ile giriş (`expo-apple-authentication`; backend `/api/auth/google`, `/api/auth/apple`; Apple id_token audience'ına `tr.ajansai.app` paket kimliğini ekle — `backend/app/services/social_auth.py`)
- [ ] Mobil: Sohbette video önerisi ve ücretsiz kullanıcı limit kartı (web `UpgradeCard` karşılığı; limit dolunca paketler gösterilsin)
- [ ] Mobil: Uygulama içi satın alma altyapısı — RevenueCat (`react-native-purchases`) ekranı ve backend webhook ucu (`/api/payments/revenuecat/webhook`: ürün kimliği → paket/ek kredi; idempotent; testli). Gerçek anahtarlar Ozan girene kadar kapalı kalsın
- [ ] Mobil: Görsel düzenleme ve video sonuçlarında "Reklam ver" kısayolu
- [ ] Backend: `/api/health/qa` raporuna son 24 saatteki üretim hata sayıları (video_tasks failed, görsel hataları) eklensin
- [ ] Web: Kütüphane ve görsel/video sonuçlarında "Reklam ver" kısayolu (mobil ile tutarlı)
- [ ] Backend (kalite, 29.10 QA raporu): Görsel denetimi Türkçe büyük İ için yanlış alarm veriyor — güzellik görselinde "PÜRÜZSÜZ CİLT" doğru (noktalı İ) yazılı olduğu hâlde denetim "CILT" diye kusur bildirdi; bu yüzden görsel boşuna yeniden üretildi (206 sn, ~2 kat maliyet) ve rapor 3/4 gösterdi. `media_qa._data_url` görseli 1024 px JPEG'e küçültüyor: denetime görseli PNG/≥1536 px gönder, ayrıca yazı bölgelerinin büyütülmüş kırpımlarını ekle; `QA_SYSTEM`'e "İ/ı, Ş, Ğ noktası/çengeli için yalnızca büyütülmüş görüntüde kesinse kusur bildir" kuralı ekle; yalnızca Türkçe karakter şikâyeti varsa yeniden üretmeden önce kırpımla ikinci bir doğrulama yap
- [ ] Backend (kalite): `media_qa.generate_checked` yeniden üretilen görseli denetlemeden döndürüyor; ikinci görseli de denetle, kusur sayısı daha az olanı seç (eşitse ilkini). Yeniden üretim istemine yalnızca doğrulanmış kusurları ekle (yanlış alarmlar isteme "CILT yazma" gibi gereksiz talimat sokuyor)
- [ ] Backend (kalite): `/api/health/qa` her görsel için ilk denemenin kusurlarını, yeniden üretim yapılıp yapılmadığını ve son denetimi ayrı alanlarda versin (`first_problems`, `retried`, `problems`); şu an `health._one_image` son görseli bağımsız ikinci kez denetliyor ve sonuçlar arasındaki farklar görünmüyor
- [ ] Backend (kalite): `media_planner` istem kuralına "başlıkta tek tip büyük/küçük harf kullan (tümü büyük ya da baş harfler büyük); small-caps veya karışık harf boyu yok" ekle — mobilya görselinde başlık "Evinize Yeni bir Hava" karışık harf boyuyla çıktı

## Ozan'a (insan gerektiren işler)

- Apple Developer hesabı (yıllık $99) → iOS TestFlight
- Google Play Console ($25) → Play iç test
- RevenueCat hesabı ve mağaza ürünleri
- Meta işletme doğrulaması sonucu → uygulama incelemesi gönderimi (`instagram_content_publish`, `instagram_manage_messages`)
