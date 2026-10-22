import type { Metadata } from "next";

import LegalPage from "../components/LegalPage";

export const metadata: Metadata = { title: "Gizlilik Politikası — ajansAI" };

export default function Privacy() {
  return (
    <LegalPage title="Gizlilik Politikası" updated="22 Ekim 2026">
      <p>
        Bu politika, ajansAI'ı (www.ajansai.tr) kullanırken hangi kişisel verilerinin işlendiğini, neden işlendiğini ve
        haklarını açıklar. 6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamında aydınlatma metni yerine de geçer.
      </p>

      <h2>Topladığımız veriler</h2>
      <ul>
        <li><strong>Hesap bilgileri:</strong> ad, e-posta adresi ve şifrenin geri döndürülemez özeti. Google ile giriş yaparsan Google'dan yalnızca adını ve e-posta adresini alırız.</li>
        <li><strong>Sohbet ve dosyalar:</strong> yazdığın mesajlar ve eklediğin görsel, belge veya videolar yanıt üretmek için işlenir. Sohbet geçmişin kendi tarayıcında saklanır; yüklediğin ve ürettiğin dosyalar bulut depomuzda tutulur.</li>
        <li><strong>Kullanım bilgileri:</strong> kredi hareketleri, ücretsiz kullanım sayaçları ve üye olmadan kullananlar için IP adresinin geri döndürülemez özeti (IP adresinin kendisi saklanmaz).</li>
        <li><strong>Ödeme bilgileri:</strong> ödemeler iyzico üzerinden alınır. Kart bilgilerin ajansAI'a ulaşmaz; biz yalnızca ödeme tutarını, durumunu ve fatura için verdiğin ad, telefon ve adresi saklarız.</li>
        <li><strong>Meta (Instagram/Facebook) bağlantısı:</strong> reklam hesabını bağlarsan Meta'nın verdiği erişim anahtarını sunucumuzda saklar, yalnızca senin isteğinle reklam hesaplarını, sayfalarını ve reklam sonuçlarını okumak ve reklam oluşturmak için kullanırız.</li>
      </ul>

      <h2>Verileri neden işliyoruz</h2>
      <ul>
        <li>Hizmeti sunmak: sohbet yanıtları, görsel ve video üretimi, reklam oluşturma.</li>
        <li>Hesabını, paketini ve kredi bakiyeni yönetmek; ödemeleri almak ve faturalandırmak.</li>
        <li>Kötüye kullanımı önlemek ve ücretsiz kullanım sınırlarını uygulamak.</li>
      </ul>
      <p>Verilerini reklam amacıyla satmayız ve üçüncü kişilere pazarlama için vermeyiz.</p>

      <h2>Verilerin aktarıldığı hizmet sağlayıcılar</h2>
      <p>Hizmeti sunabilmek için verilerin, yalnızca ilgili işlem için gerekli olduğu kadarıyla şu sağlayıcılara aktarılabilir. Bu sağlayıcıların bir kısmı yurt dışında bulunur:</p>
      <ul>
        <li>Barındırma, veritabanı ve dosya depolama: Vercel, Neon</li>
        <li>Yapay zeka modelleri: Vercel AI Gateway üzerinden Anthropic, Google, ByteDance; ayrıca Groq ve Cloudflare</li>
        <li>Stok görseller: Pixabay</li>
        <li>Ödeme: iyzico</li>
        <li>Giriş: Google (Google ile giriş yaparsan)</li>
        <li>Reklam: Meta Platforms (reklam hesabını bağlarsan)</li>
      </ul>

      <h2>Google kullanıcı verileri</h2>
      <p>
        Google ile giriş yaptığında yalnızca temel profil bilgilerini (ad, e-posta) alırız ve bunları sadece hesabını oluşturmak ve
        seni tanımak için kullanırız. ajansAI'ın Google kullanıcı verilerini kullanımı Google API Services User Data Policy'ye,
        Limited Use şartları dahil, uygundur.
      </p>

      <h2>Saklama süresi</h2>
      <p>Hesap bilgilerini hesabın açık olduğu sürece saklarız. Hesabını silmeni istediğinde verilerini 30 gün içinde sileriz; yasal olarak saklamamız gereken ödeme kayıtları ilgili süre boyunca saklanır.</p>

      <h2>Hakların</h2>
      <p>
        KVKK'nın 11. maddesi kapsamında verilerinin işlenip işlenmediğini öğrenme, bilgi isteme, düzeltilmesini veya silinmesini
        isteme ve itiraz etme hakların vardır. Taleplerin için support@ajansai.tr adresine yazabilirsin. Veri silme adımları için{" "}
        <a href="/veri-silme">veri silme sayfasına</a> bakabilirsin.
      </p>

      <h2>İletişim</h2>
      <p>Sorular için: support@ajansai.tr</p>
    </LegalPage>
  );
}
