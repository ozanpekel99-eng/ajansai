import type { Metadata } from "next";
import Link from "next/link";

import LegalPage from "../components/LegalPage";
import { LEGAL_LINKS } from "../lib/company";

export const metadata: Metadata = { title: "Yasal — ajansAI" };

export default function Legal() {
  return (
    <LegalPage title="Yasal belgeler" updated="24 Ekim 2026">
      <ul className="legal-index">
        {LEGAL_LINKS.map((l) => (
          <li key={l.href}>
            <Link href={l.href}>
              <b>{l.label}</b>
              <span>{l.desc}</span>
            </Link>
          </li>
        ))}
      </ul>
    </LegalPage>
  );
}
