# ajansAI — yapılacaklar listesi (gece geliştirme görevi buradan çalışır)

Kurallar:
- Gece görevi her çalışmada **en üstteki işaretlenmemiş** maddeyi alır, `gece/<kısa-ad>` dalında çalışır,
  testleri geçirir ve **main'e doğrudan göndermez**; pull request açar. Ozan onaylayınca birleştirilir.
- Bitirilen maddeyi `[x]` yapar ve PR bağlantısını yanına yazar (aynı PR içinde).
- Şifre, ödeme, Meta reklam yayını, mağaza gönderimi gibi işleri yapmaz; bunları "Ozan'a" bölümüne not eder.
- Bir madde tek gecede bitmeyecek kadar büyükse önce maddeyi alt adımlara böler, ilk adımı yapar.

## Sıradaki işler (öncelik sırasıyla)

- [ ] Backend (kalite, 2026-10-26 denetimi): Video başlangıç karesi en-boy oranı uyuşmazlığı — 4:5 görselden 9:16 video üretilince Veo üstte/altta 286 px siyah bant bırakıyor (içerik 1080x1348). `start_video` öncesi kaynak görsel video oranına getirilsin: ya `plan_video`'nun `frame_prompt`'u ile 9:16'ya genişletme (outpaint) düzenlemesi yapılsın, ya da oran farklıysa video oranı kaynağa eşitlensin. `health.py` qa-run'da kaynak olarak öncelikle 9:16 görsel (beyaz_esya) seçilsin; `plan["frame_prompt"]` şu an yok sayılıyor
- [ ] Backend (kalite): `media_planner.VIDEO_SYSTEM`'e kampanya görseli kuralı — başlangıç karesinde yazı/fiyat/rozet/bant varsa bunlar video boyunca tamamen sabit, net ve değişmeden kalsın; yalnızca arka plan öğeleri (konfeti, ışık parlaması, hafif kamera yaklaşması) hareket etsin; bantlar/rozetler kaydırılmasın, açılıp kapanmasın, ikonlar canlandırılmasın. (Bu sabahki videoda "ÜCRETSİZ TESLİMAT VE MONTAJ" bandı 0,25–2,0 sn arası silinip kırmızı/beyaz lekeye dönüştü, kamyon ikonu bozuldu.) Yedek istemdeki "no text" ifadesi yazılı başlangıç karesiyle çelişiyor; "keep all existing text exactly unchanged" olarak değiştirilsin
- [ ] Backend (kalite): Video otomatik denetimi — `media_qa.check_video(video_bytes, start_image, request)`: ffmpeg ile ~8 kare (ilk 2 sn'den sık) çıkarıp başlangıç karesiyle birlikte görme modeline verilsin; yazının bozulması/kaybolması, ürün/insan bozulması kontrol edilsin; `cropdetect` ile siyah bant tespiti yapılsın. Kusurda bir kez yeniden üretim, qa raporunda `video.problems` ve `video.ok` alanları (şu an videonun denetimi hiç yok, rapor her zaman "completed" diyor)
- [ ] Backend (kalite, küçük): Görsel denetim istemine (`QA_SYSTEM`) "ürün ekranlarındaki/kontrol panellerindeki anlamsız sahte yazı" maddesi; çamaşır makinesi panelinde okunamayan sahte etiketler otomatik denetimden geçti (küçük, ama yakın çekimde fark ediliyor)
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
