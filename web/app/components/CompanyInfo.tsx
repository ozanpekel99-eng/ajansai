import { COMPANY } from "../lib/company";

/** Satıcı bilgileri listesi: yalnızca doldurulmuş alanlar gösterilir. */
export default function CompanyInfo() {
  const rows: [string, string][] = [
    ["Unvan", COMPANY.legalName],
    ["Marka", COMPANY.brand],
    ["Adres", COMPANY.address],
    ["Vergi dairesi", COMPANY.taxOffice],
    ["Vergi numarası", COMPANY.taxNumber],
    ["MERSİS numarası", COMPANY.mersis],
    ["Telefon", COMPANY.phone],
    ["E-posta", COMPANY.email],
    ["Web sitesi", COMPANY.website],
  ];
  return (
    <dl className="company-info">
      {rows
        .filter(([, v]) => v)
        .map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
    </dl>
  );
}
