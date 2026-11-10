"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { CitationAudit } from "@/lib/types";
import { Quote } from "lucide-react";
import { useState } from "react";

function Group({ title, tone, children }: { title: string; tone: "bad" | "warn"; children: React.ReactNode }) {
  return (
    <div className={`rounded-btn border p-3 ${tone === "bad" ? "border-vermillion/30 bg-vermillion/5" : "border-saffron/40 bg-saffron/5"}`}>
      <p className="font-semibold">{title}</p>
      <ul className="mt-1.5 space-y-1 text-[13px] text-black/75">{children}</ul>
    </div>
  );
}

/** Konsistensi sitasi: sitasi di teks vs daftar rujukan terpilih, rujukan tak terpakai, tahun salah, dan campuran gaya. */
export function CitationAuditCard() {
  const project = useProject((s) => s.project);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [r, setR] = useState<CitationAudit | null>(null);
  if (!project) return null;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setR(await api.citationAudit(project.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Pemeriksaan gagal");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <Pill tone="blue">
        <Quote size={12} /> Sitasi
      </Pill>
      <h2 className="t-heading-sm mt-3">Konsistensi sitasi dan daftar pustaka</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Mencocokkan setiap sitasi di naskah dengan rujukan terpilih (nama belakang dan tahun), mencari rujukan yang tidak pernah dikutip, tahun yang salah, dan campuran gaya penulisan. Dihitung langsung, tanpa LLM.
      </p>
      <Button className="mt-4" onClick={run} loading={busy}>
        {!busy && <Quote size={15} />} Periksa sitasi
      </Button>
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}
      {r && (
        <div className="mt-4 space-y-3 text-[13px]">
          <p className="text-black/60">
            {r.in_text_citations} sitasi di teks, {r.references} rujukan terpilih, gaya {r.style === "IEEE" ? "IEEE" : "penulis-tahun"}.
          </p>
          {r.ok && <p className="rounded-btn bg-[#f0faf0] p-3 text-[#0a4d1e]">Semua sitasi cocok dengan daftar rujukan dan tidak ada rujukan yang menganggur.</p>}
          {r.unknown.length > 0 && (
            <Group title={`${r.unknown.length} sitasi tidak ada di daftar rujukan`} tone="bad">
              {r.unknown.map((u, i) => (
                <li key={i}>
                  {u.text} · subbab {u.section}
                  {u.own_writing ? " (tulisan Anda)" : ""}
                </li>
              ))}
            </Group>
          )}
          {r.year_mismatch.length > 0 && (
            <Group title={`${r.year_mismatch.length} sitasi dengan tahun yang tidak cocok`} tone="bad">
              {r.year_mismatch.map((u, i) => (
                <li key={i}>
                  {u.text} · subbab {u.section}; di daftar rujukan tahunnya {u.listed_years.join(", ")}
                </li>
              ))}
            </Group>
          )}
          {r.numeric_out_of_range.length > 0 && (
            <Group title="Nomor sitasi di luar daftar rujukan" tone="bad">
              {r.numeric_out_of_range.map((u, i) => (
                <li key={i}>
                  {u.text} · subbab {u.section}: tidak ada rujukan nomor {u.number}
                </li>
              ))}
            </Group>
          )}
          {r.uncited.length > 0 && (
            <Group title={`${r.uncited.length} rujukan terpilih tidak pernah dikutip`} tone="warn">
              {r.uncited.map((u, i) => (
                <li key={i}>
                  {u.authors[0]} ({u.year}). {u.title}
                </li>
              ))}
              <li className="text-black/50">Kutip di naskah atau hapus dari pilihan rujukan agar daftar pustaka bersih.</li>
            </Group>
          )}
          {r.style_issues.length > 0 && (
            <Group title="Gaya sitasi" tone="warn">
              {r.style_issues.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </Group>
          )}
          {r.duplicates.length > 0 && (
            <Group title="Rujukan ganda" tone="warn">
              {r.duplicates.map((d, i) => (
                <li key={i}>
                  {d.title} (sama dengan: {d.same_as})
                </li>
              ))}
            </Group>
          )}
          {(r.weak.no_authors.length > 0 || r.weak.no_year.length > 0) && (
            <Group title="Data rujukan kurang lengkap" tone="warn">
              {r.weak.no_authors.map((t) => (
                <li key={`a${t}`}>Tanpa penulis: {t}</li>
              ))}
              {r.weak.no_year.map((t) => (
                <li key={`y${t}`}>Tanpa tahun: {t}</li>
              ))}
            </Group>
          )}
        </div>
      )}
    </Card>
  );
}
