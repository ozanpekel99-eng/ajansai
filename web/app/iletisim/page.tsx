import type { Metadata } from "next";

import CompanyInfo from "../components/CompanyInfo";
import LegalPage from "../components/LegalPage";
import { COMPANY } from "../lib/company";

export const metadata: Metadata = { title: "İletişim — ajansAI" };

export default function Contact() {
  return (
    <LegalPage title="İletişim" updated="23 Ekim 2026">
      <p>
        Paketler, ödemeler, iade talepleri ve teknik destek için bize e-postayla ulaşabilirsin. Mesajlarına iş günlerinde
        en geç 24 saat içinde yanıt veririz.
      </p>
      <h2>Destek</h2>
      <p>
        E-posta: <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a>
        {COMPANY.phone && (
          <>
            <br />
            Telefon: <a href={`tel:${COMPANY.phone.replace(/\s/g, "")}`}>{COMPANY.phone}</a> (hafta içi 09.00–18.00)
          </>
        )}
      </p>
      <h2>Şirket bilgileri</h2>
      <CompanyInfo />
    </LegalPage>
  );
}
