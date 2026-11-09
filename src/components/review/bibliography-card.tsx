"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { buildBibliography, citationOrder, runsToText } from "@/lib/citation";
import type { CitationStyle, ThesisProject } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BookMarked, Check, Copy } from "lucide-react";
import { useMemo, useState } from "react";

const STYLE_LABEL: Record<CitationStyle, string> = {
  APA_7TH: "APA 7th",
  IEEE: "IEEE",
  CHICAGO: "Chicago",
  HARVARD: "Harvard",
};

export function BibliographyCard({ project }: { project: ThesisProject }) {
  const templateStyle = project.template.citation_style;
  const [override, setOverride] = useState<CitationStyle | null>(null);
  const [copied, setCopied] = useState(false);
  const style = override ?? templateStyle;

  const selected = useMemo(
    () => project.references.filter((r) => project.selectedRefIds.includes(r.id)),
    [project.references, project.selectedRefIds]
  );
  const entries = useMemo(() => buildBibliography(selected, style, project.sections), [selected, style, project.sections]);
  const citedIds = useMemo(() => new Set(citationOrder(project.sections)), [project.sections]);
  const uncited = selected.filter((r) => citedIds.size > 0 && !citedIds.has(r.id));

  const copy = async () => {
    const text = entries.map((e) => `${e.label ? `${e.label} ` : ""}${runsToText(e.runs)}`).join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard diblokir: pengguna masih bisa menyalin manual dari daftar */
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BookMarked size={17} className="text-brand" />
          <h2 className="t-heading-sm">Daftar pustaka otomatis</h2>
          <Pill>{entries.length} entri</Pill>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-btn bg-black/5 p-0.5 text-[12px] font-medium" role="group" aria-label="Gaya sitasi">
            {(["APA_7TH", "IEEE"] as CitationStyle[]).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setOverride(s === templateStyle ? null : s)}
                className={cn("rounded-btn px-3 py-2.5 transition-colors sm:py-1.5", style === s ? "bg-white shadow-sm" : "text-black/55")}
              >
                {STYLE_LABEL[s]}
              </button>
            ))}
          </div>
          <Button variant="ghost" size="sm" onClick={copy} disabled={entries.length === 0}>
            {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Tersalin" : "Salin semua"}
          </Button>
        </div>
      </div>

      <p className="mt-2 text-[12px] text-black/50">
        Templat kampus memakai {STYLE_LABEL[templateStyle]}; naskah dan ekspor .docx mengikuti gaya itu.
        {style !== templateStyle && " Gaya di atas hanya pratinjau dan untuk disalin."} Hanya rujukan yang dikutip di naskah yang dimasukkan
        {style === "IEEE" ? "; nomor [n] mengikuti urutan kemunculan di seluruh dokumen." : ", berurut abjad."}
      </p>

      {entries.length === 0 ? (
        <p className="mt-4 rounded-btn border border-dashed border-hairline p-4 text-center text-[13px] text-black/45">
          Belum ada rujukan terpilih. Pilih rujukan di Langkah 3, lalu buat draf di Langkah 4.
        </p>
      ) : (
        <ol className="mt-4 space-y-3 text-[13.5px] leading-relaxed text-charcoal">
          {entries.map((e) => (
            <li key={e.ref.id} className="flex gap-2 pl-6 -indent-6">
              {e.label && <span className="w-6 shrink-0 font-medium text-black/50">{e.label}</span>}
              <span>
                {e.runs.map((r, i) => (r.italic ? <em key={i}>{r.text}</em> : <span key={i}>{r.text}</span>))}
                {!e.ref.doi && <span className="ml-2 rounded-pill bg-saffron/15 px-2 py-0.5 text-[11px] text-[#6b4a00]">tanpa DOI</span>}
                {!e.ref.pages && <span className="ml-1 rounded-pill bg-black/5 px-2 py-0.5 text-[11px] text-black/50">tanpa halaman</span>}
              </span>
            </li>
          ))}
        </ol>
      )}

      {uncited.length > 0 && (
        <p className="mt-4 rounded-btn border border-saffron/40 bg-saffron/5 p-3 text-[12.5px] text-[#6b4a00]">
          {uncited.length} rujukan terpilih belum dikutip di naskah dan tidak masuk daftar: {uncited.map((r) => r.title).slice(0, 3).join("; ")}
          {uncited.length > 3 ? "; …" : ""}.
        </p>
      )}
    </Card>
  );
}
