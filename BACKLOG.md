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
- [ ] Backend (kalite, 09.11 denetimi — öncelikli): QA videosunun son ~0,4 sn'sinde "PEŞİN FİYATINA 9 TAKSİT" etiketi küçülüp aşağı kayıyor, son karede okunamaz harf yığınına dönüşüyor (0–5,5 sn yazılar sağlam). Ayrıca 1,2–2,4 sn arasında konfeti "10.000 TL İNDİRİM" yazısının üstünden geçiyor. Sebep: `media_planner.VIDEO_SYSTEM` "No on-screen text, captions, logos" diyor ama QA videosu yazılı bir kampanya afişinden başlıyor; model yazıları korumak zorunda olduğunu bilmiyor. Düzeltme: başlangıç karesinde yazı/rozet/fiyat etiketi varsa şu kuralı ekle — "All texts, badges and price tags already in the start frame are part of the poster: keep them fixed in place, same size, sharp and fully legible from the first to the LAST frame; animate only the product scene subtly (light, soft reflections); no zoom-out, no camera move at the end; confetti/particles never pass over text." (26.10'daki VIDEO_SYSTEM maddesi hâlâ birleştirilmedi; bu hata bu yüzden sürüyor.)
- [ ] Backend (kalite): Video son-kare güvencesi — `check_video` gelene kadar ucuz önlem: Veo çıktısının son karesini başlangıç karesiyle karşılaştır (yazı bölgelerinde SSIM/fark); son 0,5 sn'de bozulma varsa videoyu son sağlam karede kesip o kareyi tutarak (`ffmpeg tpad=stop_mode=clone`) süreyi koru. Kullanıcıya bozuk kapanış karesi gitmez; ek üretim maliyeti yok.
- [ ] Backend (kalite): Görsel denetimi tutarsız — mobilya görseli tek üretimde (50,7 sn) geldi, yani `generate_checked` içindeki ilk denetim sorunsuz dedi; `qa-run`'daki ikinci denetim aynı görselde "HAYALINIZDEKI" (noktasız büyük İ) hatasını buldu ve kullanıcı bu hatalı görseli almış olurdu. Düzeltme: (1) `QA_SYSTEM`'e 7. madde: "Turkish capitals: compare each word with the quoted text letter by letter; a dotless capital I where the text has İ (e.g. HAYALİNİZDEKİ, ÜCRETSİZ) is a misspelling"; (2) denetim çağrısında temperature=0; (3) `direct_ad_prompt` başlıkta İ geçen her kelime için "the capital İ letters carry a dot above them" notu eklesin.
- [ ] Backend (kalite, 05.11'den sonra 2. kez): Aynı yazının tekrarı sürüyor — beyaz eşyada "İKİLİ ALIMDA FIRSAT" başlığının hemen altında yine "İKİLİ ALIMDA"; kafede "YENİ SEZON" üst kurdelede ve fiyat kutusunda ("YENİ SEZON FİYATI"). `AD_DIRECTOR_SYSTEM`'e "Each phrase appears only once on the poster; the hero headline must not repeat words of the offer line" kuralı, `QA_SYSTEM`'e "same phrase rendered twice" kusur maddesi.
- [ ] Backend (kalite, küçük): Bundle "+" rozeti kırmızı daire içinde beyaz haç olarak çiziliyor (ilk yardım / İsviçre bayrağı gibi duruyor). `AD_DIRECTOR_SYSTEM`'deki '"+" combo badge' ifadesini "a gold or brand-colored plus sign badge (not a white cross on red)" yap.
- [ ] Backend (kalite, küçük): `/api/health/qa` raporuna videonun Veo istemini (`plan["prompt"]`) ve kullanılan başlangıç karesi adresini ekle; video kusurlarının istemden mi modelden mi geldiği raporda görülebilsin.

## Ozan'a (insan gerektiren işler)

- Apple Developer hesabı (yıllık $99) → iOS TestFlight
- Google Play Console ($25) → Play iç test
- RevenueCat hesabı ve mağaza ürünleri
- Meta işletme doğrulaması sonucu → uygulama incelemesi gönderimi (`instagram_content_publish`, `instagram_manage_messages`)
