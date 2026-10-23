import type { Metadata } from "next";
import Link from "next/link";

import LegalPage from "../components/LegalPage";
import { COMPANY } from "../lib/company";

export const metadata: Metadata = { title: "Teslimat ve İade — ajansAI" };

export default function DeliveryRefund() {
  return (
    <LegalPage title="Teslimat ve İade Koşulları" updated="23 Ekim 2026">
      <p>
        ajansAI, internet üzerinden sunulan dijital bir hizmettir. Satın aldığın paketler ve ek krediler fiziksel bir ürün
        değildir; kargo ile gönderilmez.
      </p>

      <h2>Teslimat</h2>
      <ul>
        <li>Ödemen iyzico tarafından onaylandığı anda paketin ve kredilerin hesabına tanımlanır. Ayrıca bir teslimat süresi yoktur.</li>
        <li>Satın alma sonrası ödeme bilgilerini içeren bir onay e-postası, hesabına kayıtlı e-posta adresine gönderilir.</li>
        <li>Paket ödeme onayına rağmen hesabına tanımlanmadıysa {COMPANY.email} adresine yaz; en geç 24 saat içinde tanımlanır ya da ücretin iade edilir.</li>
      </ul>

      <h2>Paket süresi ve iptal</h2>
      <ul>
        <li>Aylık paketler 30 gün, yıllık paketler 365 gün geçerlidir. Paketler otomatik yenilenmez; kartından kendiliğinden ödeme alınmaz.</li>
        <li>Paketini iptal etmek için ayrıca bir işlem yapman gerekmez: süre bitince paket yenilenmez ve hesabın ücretsiz pakete döner.</li>
        <li>Hesabını tamamen kapatmak istersen <Link href="/veri-silme">hesap ve veri silme</Link> adımlarını izleyebilirsin.</li>
      </ul>

      <h2>İade şartları</h2>
      <ul>
        <li>
          <strong>Kullanılmamış paket:</strong> Satın alma tarihinden itibaren 14 gün içinde, paketin kredilerinden hiç
          kullanmadıysan ücretin tamamı iade edilir.
        </li>
        <li>
          <strong>Kullanılmış paket:</strong> Krediler anında kullanıma açılan dijital hizmettir. Kredilerden bir kısmı
          kullanıldıktan sonra, 6502 sayılı Tüketicinin Korunması Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği'nin
          15. maddesi (elektronik ortamda anında ifa edilen hizmetler) uyarınca cayma hakkı kullanılamaz ve iade yapılmaz.
        </li>
        <li>
          <strong>Ek kredi paketleri:</strong> Hiç kullanılmamışsa 14 gün içinde tam iade edilir; kullanıldıktan sonra iade edilmez.
        </li>
        <li>
          <strong>Hatalı veya mükerrer ödeme:</strong> Aynı paket için birden fazla ödeme alındıysa ya da teknik bir hata
          nedeniyle paket tanımlanmadıysa ücretin tamamı iade edilir.
        </li>
        <li>
          <strong>Başarısız üretim:</strong> Görsel, video veya dosya üretimi teknik bir hata nedeniyle başarısız olursa
          harcanan kredi otomatik olarak hesabına geri yüklenir.
        </li>
      </ul>

      <h2>İade nasıl yapılır</h2>
      <ol>
        <li>Hesabına kayıtlı e-posta adresinden {COMPANY.email} adresine "İade talebi" konulu bir e-posta gönder; ödeme tarihini ve paketin adını yaz.</li>
        <li>Talebin en geç 3 iş günü içinde değerlendirilir ve sonucu e-postayla bildirilir.</li>
        <li>Onaylanan iadeler, ödemeyi yaptığın karta iyzico üzerinden yapılır. Tutarın kartına yansıması bankana bağlı olarak 2–10 iş günü sürebilir.</li>
        <li>İade onaylandığında ilgili paket ve krediler hesabından kaldırılır.</li>
      </ol>

      <p>
        Satış koşullarının tamamı için <Link href="/mesafeli-satis-sozlesmesi">Mesafeli Satış Sözleşmesi</Link>'ne,
        sorular için <Link href="/iletisim">İletişim</Link> sayfasına bakabilirsin.
      </p>
    </LegalPage>
  );
}
