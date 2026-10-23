import type { Metadata } from "next";
import Link from "next/link";

import CompanyInfo from "../components/CompanyInfo";
import LegalPage from "../components/LegalPage";
import { COMPANY } from "../lib/company";

export const metadata: Metadata = { title: "Mesafeli Satış Sözleşmesi — ajansAI" };

export default function DistanceSales() {
  return (
    <LegalPage title="Mesafeli Satış Sözleşmesi" updated="23 Ekim 2026">
      <h2>1. Taraflar</h2>
      <p>
        <strong>Satıcı:</strong>
      </p>
      <CompanyInfo withAddress />
      <p>
        <strong>Alıcı:</strong> {COMPANY.website} adresinde üyelik oluşturan ve ödeme sayfasında ad, soyad, telefon ve
        adres bilgilerini giren kişi. Alıcı bilgileri ödeme sırasında verilen bilgilerdir.
      </p>

      <h2>2. Sözleşmenin konusu</h2>
      <p>
        Bu sözleşme, Alıcı'nın {COMPANY.website} üzerinden elektronik ortamda satın aldığı yapay zeka destekli içerik üretim
        hizmeti paketinin (aylık veya yıllık paket ya da ek kredi paketi) satışı ve ifasına ilişkin olarak 6502 sayılı
        Tüketicinin Korunması Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği hükümleri gereğince tarafların hak ve
        yükümlülüklerini düzenler.
      </p>

      <h2>3. Hizmetin temel nitelikleri ve bedeli</h2>
      <ul>
        <li>Satın alınan paketin adı, süresi, içerdiği kredi miktarı, KDV hariç bedeli, KDV tutarı ve KDV dahil toplam bedeli ödeme sayfasında, ödemeden önce Alıcı'ya gösterilir.</li>
        <li>Bedeller ABD doları (USD) cinsinden belirlenir ve %20 KDV eklenir. Ödeme, ödeme günündeki T.C. Merkez Bankası döviz satış kuru ile Türk lirasına çevrilerek TL olarak tahsil edilir; çekilecek TL tutarı ödeme ekranında gösterilir.</li>
        <li>Paketler otomatik yenilenmez; dönem sonunda Alıcı'dan kendiliğinden ödeme alınmaz.</li>
      </ul>

      <h2>4. Ödeme</h2>
      <p>
        Ödeme, lisanslı ödeme kuruluşu iyzico (İyzi Ödeme ve Elektronik Para Hizmetleri A.Ş.) altyapısı üzerinden kredi
        veya banka kartıyla alınır. Kart bilgileri Satıcı tarafından görülmez ve saklanmaz.
      </p>

      <h2>5. İfa ve teslimat</h2>
      <p>
        Hizmet dijitaldir ve fiziksel teslimat yapılmaz. Ödemenin onaylanmasıyla paket ve krediler Alıcı'nın hesabına
        anında tanımlanır; bu an sözleşmenin ifa edildiği andır. Ayrıntılar{" "}
        <Link href="/teslimat-ve-iade">Teslimat ve İade Koşulları</Link>'nda yer alır.
      </p>

      <h2>6. Cayma hakkı</h2>
      <ul>
        <li>
          Mesafeli Sözleşmeler Yönetmeliği'nin 15. maddesinin (ğ) bendi uyarınca, elektronik ortamda anında ifa edilen
          hizmetlerde ve tüketiciye anında teslim edilen gayrimaddi mallarda cayma hakkı bulunmaz. Alıcı, ödeme öncesinde
          bu sözleşmeyi onaylayarak hizmetin anında ifasına onay verdiğini ve kullanım başladıktan sonra cayma hakkını
          kaybedeceğini kabul eder.
        </li>
        <li>
          Buna rağmen Satıcı, kredilerinden hiç kullanılmamış paketler için satın alma tarihinden itibaren 14 gün içinde
          yapılan iade taleplerinde bedelin tamamını iade eder. İade adımları Teslimat ve İade Koşulları'nda açıklanmıştır.
        </li>
      </ul>

      <h2>7. Tarafların yükümlülükleri</h2>
      <ul>
        <li>Satıcı, hizmeti sitede tanıtıldığı nitelikte sunmakla ve teknik bir hata nedeniyle başarısız olan üretimlerde harcanan krediyi iade etmekle yükümlüdür.</li>
        <li>Alıcı, hizmeti <Link href="/kosullar">Kullanım Koşulları</Link>'na uygun kullanmakla ve ödeme sırasında doğru bilgi vermekle yükümlüdür.</li>
      </ul>

      <h2>8. Uyuşmazlıkların çözümü</h2>
      <p>
        Bu sözleşmeden doğan uyuşmazlıklarda, Ticaret Bakanlığı'nca her yıl ilan edilen parasal sınırlar dahilinde Alıcı'nın
        yerleşim yerindeki veya hizmeti satın aldığı yerdeki tüketici hakem heyetleri, bu sınırları aşan uyuşmazlıklarda
        tüketici mahkemeleri yetkilidir.
      </p>

      <h2>9. Yürürlük</h2>
      <p>
        Alıcı, ödeme sayfasında bu sözleşmeyi ve Teslimat ve İade Koşulları'nı okuduğunu onaylayarak ödemeyi
        tamamladığında sözleşme elektronik ortamda kurulmuş olur. Sözleşmenin bir kopyasına bu sayfadan her zaman
        ulaşılabilir.
      </p>
    </LegalPage>
  );
}
