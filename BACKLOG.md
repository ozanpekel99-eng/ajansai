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
- [ ] Ozan'a / birleştirme (kalite, 12.11 denetimi — öncelikli): 28.10'dan beri main'e hiçbir kalite düzeltmesi girmedi; aynı hatalar her sabah tekrar ediyor ama düzeltme kodları hazır bekliyor. Önerilen birleştirme sırası: #24 (Türkçe İ yanlış alarmı, yüksek çözünürlüklü denetim) → #23 (panelde sahte yazı/logo) → #29 (aynı yazının tekrarı) → #26 (yeniden üretilen görselin de denetlenmesi). Bu dördü, 12.11 raporundaki tüm görsel bulgularını karşılıyor.
- [ ] Backend (kalite, 12.11 — 29.10 ve 09.11'den sonra 3. kez): Otomatik denetim doğru yazılmış "HAYALİNİZDEKİ" başlığını "noktasız İ" diye kusurlu saydı (görsel 2x büyütülerek elle kontrol edildi: üç İ'nin de noktası var). Mobilya üretimi 84,9 sn sürdü (diğerleri ~45 sn), yani `generate_checked` yanlış alarm yüzünden görseli boşuna bir kez daha üretti (ek maliyet + bekleme). 09.11 maddesi (PR #28) bu hatayı gerçek sanıp QA'ya "dotless I is a misspelling" kuralı eklemeyi önermişti; bu yanlış alarmı artırır, **o öneri (1. alt madde) uygulanmasın**. Doğru düzeltme PR #24 (1568 px PNG + "Türkçe harf uygunsa doğrudur" kuralı); ek olarak 3/3 adımı: yalnızca Türkçe karakter şikâyeti varsa başlık bölgesinin 2x kırpımıyla ikinci bir doğrulama yapılsın, doğrulanmazsa yeniden üretim yapılmasın.
- [ ] Backend (kalite, 09.11'den sonra 2. kez): Beyaz eşyada "+" paket rozeti yine kırmızı daire içinde beyaz haç (ilk yardım işareti gibi). Hiçbir açık PR karşılamıyor. `media_planner.AD_DIRECTOR_SYSTEM` satır ~127'deki '"+" combo badge for bundles' ifadesi → '"+" combo badge for bundles (a gold or brand-colored plus sign, never a white cross on a red circle)'. Aynı görselde "İKİLİ" kelimesi üç kez geçiyor (kurdele, başlık "İKİLİ GÜÇ", fiyat etiketi); sebebi aynı satırlardaki "EVİNİZİN İKİ GÜÇLÜSÜ" örnek başlığı — örnek, teklif satırıyla kelime paylaşmayan bir başlıkla değiştirilsin (PR #29'un tekrar kuralıyla birlikte).

## Ozan'a (insan gerektiren işler)

- Apple Developer hesabı (yıllık $99) → iOS TestFlight
- Google Play Console ($25) → Play iç test
- RevenueCat hesabı ve mağaza ürünleri
- Meta işletme doğrulaması sonucu → uygulama incelemesi gönderimi (`instagram_content_publish`, `instagram_manage_messages`)
