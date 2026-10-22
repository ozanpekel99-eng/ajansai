import type { Metadata } from "next";

import LegalPage from "../components/LegalPage";

export const metadata: Metadata = { title: "Veri Silme — ajansAI" };

export default function DataDeletion() {
  return (
    <LegalPage title="Verilerini silme" updated="22 Ekim 2026">
      <p>Hesabını ve ajansAI'daki verilerini istediğin zaman sildirebilirsin.</p>
      <ol>
        <li>Hesabına kayıtlı e-posta adresinden support@ajansai.tr adresine "Hesabımı sil" konulu bir e-posta gönder.</li>
        <li>Hesabın, sohbet ve kullanım kayıtların, yüklediğin ve ürettiğin dosyalar ve bağladığın Meta erişim anahtarı 30 gün içinde silinir.</li>
        <li>Yasal olarak saklamamız gereken ödeme kayıtları ilgili süre boyunca saklanır.</li>
      </ol>
      <p>
        Yalnızca Meta (Facebook/Instagram) bağlantısını kaldırmak istersen ajansAI'da Reklamlar sayfasından bağlantıyı
        kesebilir ya da Facebook'ta Ayarlar → Güvenlik ve giriş → İş Entegrasyonları bölümünden ajansAI'ı kaldırabilirsin.
      </p>
    </LegalPage>
  );
}
