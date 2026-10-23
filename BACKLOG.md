# ajansAI — yapılacaklar listesi (gece geliştirme görevi buradan çalışır)

Kurallar:
- Gece görevi her çalışmada **en üstteki işaretlenmemiş** maddeyi alır, `gece/<kısa-ad>` dalında çalışır,
  testleri geçirir ve **main'e doğrudan göndermez**; pull request açar. Ozan onaylayınca birleştirilir.
- Bitirilen maddeyi `[x]` yapar ve PR bağlantısını yanına yazar (aynı PR içinde).
- Şifre, ödeme, Meta reklam yayını, mağaza gönderimi gibi işleri yapmaz; bunları "Ozan'a" bölümüne not eder.
- Bir madde tek gecede bitmeyecek kadar büyükse önce maddeyi alt adımlara böler, ilk adımı yapar.

## Sıradaki işler (öncelik sırasıyla)

- [ ] Backend+Web (yönetici): Sosyal medya yayın kuyruğu — `marketing/<hafta>/plan.json`'daki onaylı paylaşımları yöneticinin kayıtlı Meta bağlantısıyla Instagram @ajansai.tr hesabına planlı saatinde paylaşan Vercel Cron (Instagram Graph API: görsel, carousel, Reels; `instagram_content_publish` izni gerekir), web'de yöneticiye özel onay sayfası (her gönderi: onayla / düzenle / atla) ve paylaşım sonrası etkileşim özetinin günlük rapora eklenmesi. Meta reklamları (Ajans AI reklam hesabı act_1823149412206641, yalnızca Instagram yerleşimi, günlük 1.000 TL, hedef satın alma, piksel 1084755444379431) için günlük performans özeti ve öneri; bütçe/kampanya değişikliği yalnızca Ozan onayıyla
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
- Meta işletme doğrulaması sonucu → uygulama incelemesi gönderimi
