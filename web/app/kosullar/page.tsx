import type { Metadata } from "next";

import LegalPage from "../components/LegalPage";

export const metadata: Metadata = { title: "Kullanım Koşulları — ajansAI" };

export default function Terms() {
  return (
    <LegalPage title="Kullanım Koşulları" updated="22 Ekim 2026">
      <p>ajansAI'ı (www.ajansai.tr) kullanarak bu koşulları kabul etmiş olursun.</p>

      <h2>Hizmet</h2>
      <p>
        ajansAI; yapay zeka destekli sohbet, görsel ve video üretimi ile Instagram reklamı oluşturma araçları sunar. Yapay zeka
        yanıtları hatalı veya eksik olabilir; önemli bilgileri ve yayınlayacağın içerikleri kontrol etmek senin sorumluluğundadır.
      </p>

      <h2>Hesap</h2>
      <ul>
        <li>Hesabını açarken doğru bilgi vermeli ve giriş bilgilerini korumalısın.</li>
        <li>Hesabında yapılan işlemlerden sen sorumlusun.</li>
      </ul>

      <h2>Paketler, krediler ve ödeme</h2>
      <ul>
        <li>Ücretli paketler aylık (30 gün) veya yıllık (365 gün) olarak satılır, otomatik yenilenmez. Fiyatlara KDV eklenir.</li>
        <li>Krediler her 30 günde yenilenir; kullanılmayan kredi sonraki döneme devretmez.</li>
        <li>Üretim teknik bir hata nedeniyle başarısız olursa harcanan kredi otomatik iade edilir.</li>
        <li>Ödemeler iyzico üzerinden ABD doları olarak alınır. İade ve cayma talepleri için destek@ajansai.tr adresine yazabilirsin; kullanılmamış paketler için talepler mevzuata uygun şekilde değerlendirilir.</li>
        <li>Ücretsiz paketin kullanım sınırları önceden haber verilerek değiştirilebilir.</li>
      </ul>

      <h2>İçerik ve kullanım kuralları</h2>
      <ul>
        <li>Ürettiğin içerikleri ticari olarak kullanabilirsin. Yüklediğin dosyaları kullanma hakkına sahip olmalısın.</li>
        <li>Hizmeti hukuka aykırı, yanıltıcı, nefret söylemi içeren, başkalarının haklarını ihlal eden veya müstehcen içerik üretmek için kullanamazsın.</li>
        <li>Meta reklamları Meta'nın reklam politikalarına tabidir; reklam bütçesi kendi Meta hesabından harcanır ve sorumluluğu sana aittir.</li>
        <li>Kurallara aykırı kullanımda hesabını askıya alabilir veya kapatabiliriz.</li>
      </ul>

      <h2>Sorumluluğun sınırı</h2>
      <p>
        Hizmet olduğu gibi sunulur. Yasaların izin verdiği ölçüde, hizmetin kullanımından doğan dolaylı zararlardan sorumlu
        değiliz; sorumluluğumuz her durumda son 12 ayda bize ödediğin tutarla sınırlıdır.
      </p>

      <h2>Değişiklikler ve iletişim</h2>
      <p>Bu koşulları güncelleyebiliriz; önemli değişiklikleri sitede duyururuz. Sorular için: destek@ajansai.tr</p>
    </LegalPage>
  );
}
