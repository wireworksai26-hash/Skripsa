"use client";

import { ButtonLink } from "@/components/ui/button";
import { BookOpen, FlaskConical, GraduationCap, Layers } from "lucide-react";
import { useState } from "react";

/** Struktur bab sama persis dengan templat bawaan di backend (backend/app/services/templates.py). */
const TABS = [
  {
    id: "kuantitatif",
    label: "Kuantitatif",
    icon: FlaskConical,
    note: "Pengaruh X terhadap Y dengan hipotesis, instrumen, dan uji statistik. 18 subbab.",
    chapters: [
      ["I · Pendahuluan", "Latar belakang · Rumusan · Tujuan · Manfaat · Batasan"],
      ["II · Kajian Pustaka", "Tinjauan pustaka · Kerangka pemikiran · Hipotesis"],
      ["III · Metode", "Desain · Populasi dan sampel · Pengumpulan data · Instrumen · Analisis"],
      ["IV · Hasil dan Pembahasan", "Gambaran objek · Hasil pengujian · Pembahasan"],
      ["V · Simpulan dan Saran", "Kesimpulan · Saran"],
    ],
  },
  {
    id: "kualitatif",
    label: "Kualitatif",
    icon: BookOpen,
    note: "Fenomenologi, studi kasus, atau analisis isi dengan keabsahan data. 19 subbab.",
    chapters: [
      ["I · Pendahuluan", "Latar belakang · Fokus penelitian · Rumusan · Tujuan · Manfaat"],
      ["II · Kajian Pustaka", "Landasan teori · Definisi operasional · Penelitian relevan · Kerangka konseptual"],
      ["III · Metode", "Pendekatan · Sumber data · Instrumen · Pengumpulan · Keabsahan data · Analisis"],
      ["IV · Hasil dan Pembahasan", "Temuan penelitian · Pembahasan"],
      ["V · Simpulan dan Saran", "Simpulan · Saran"],
    ],
  },
  {
    id: "campuran",
    label: "Mixed methods & R&D",
    icon: Layers,
    note: "Memakai kerangka kuantitatif; saran tabel dan diagram AI menyesuaikan desain bertahap, validasi ahli, dan uji coba.",
    chapters: [
      ["I–II", "Pendahuluan dan kajian pustaka seperti kerangka kuantitatif"],
      ["III · Metode", "Desain bertahap, instrumen, dan teknik analisis"],
      ["IV · Hasil", "Tabel profil, joint display, atau hasil validasi ahli dari Saran AI"],
      ["V · Simpulan", "Kesimpulan dan saran"],
    ],
  },
  {
    id: "s2",
    label: "Tesis S2",
    icon: GraduationCap,
    note: "Format makalah pascasarjana yang ringkas. 9 subbab.",
    chapters: [
      ["I · Pendahuluan", "Latar belakang · Rumusan masalah dan tujuan"],
      ["II · Kajian Pustaka", "Kajian literatur krusial · State of the art dan research gap"],
      ["III · Metode", "Kerangka metodologi · Instrumen dan validasi"],
      ["IV · Hasil dan Pembahasan", "Analisis dan interpretasi · Diskusi kritis"],
      ["V · Simpulan", "Simpulan dan implikasi"],
    ],
  },
] as const;

export function ResearchTabs() {
  const [active, setActive] = useState<(typeof TABS)[number]["id"]>("kuantitatif");
  const tab = TABS.find((t) => t.id === active) ?? TABS[0];

  return (
    <div className="mt-8">
      <div role="tablist" aria-label="Desain penelitian" className="scroll-thin flex gap-1.5 overflow-x-auto rounded-card border border-hairline bg-white p-1.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={active === t.id}
            aria-controls="research-panel"
            onClick={() => setActive(t.id)}
            className={`inline-flex min-h-10 shrink-0 items-center gap-2 rounded-btn px-4 text-[14px] font-medium transition-colors ${active === t.id ? "bg-brand text-white" : "text-black/65 hover:bg-black/5"}`}
          >
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      <div id="research-panel" role="tabpanel" className="mt-4 grid gap-6 rounded-card border border-hairline bg-white p-5 sm:p-7 md:grid-cols-[1fr_1.4fr]">
        <div>
          <h3 className="t-heading-sm">{tab.label}</h3>
          <p className="mt-2 text-[14.5px] leading-relaxed text-graphite">{tab.note}</p>
          <ButtonLink className="mt-5" variant="primary" href="/proyek/1-inisiasi">
            Mulai dengan desain ini
          </ButtonLink>
        </div>
        <ol className="space-y-2">
          {tab.chapters.map(([title, sub]) => (
            <li key={title} className="rounded-btn border border-hairline bg-canvas p-3">
              <p className="text-[14px] font-semibold">{title}</p>
              <p className="mt-0.5 text-[12.5px] leading-relaxed text-black/60">{sub}</p>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
