"use client";

import { Input } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import type { LedgerEntry } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChevronDown, ExternalLink, Search } from "lucide-react";
import { useMemo, useState } from "react";

const MARKS = new RegExp("[" + String.fromCharCode(0x300) + "-" + String.fromCharCode(0x36f) + "]", "g");
const fold = (s: string) => s.normalize("NFKD").replace(MARKS, "").toLowerCase();

const where = (section: string, title: string) => (section === "-" ? "Naskah" : `Subbab ${section}${title ? ` ${title}` : ""}`);

function haystack(e: LedgerEntry): string {
  return fold([e.reference, e.short, e.title, e.evidence, e.doi, e.source, ...e.uses.map((u) => `${u.section} ${u.title} ${u.sentence}`)].join(" "));
}

/** Daftar rujukan yang bisa dicari: ketik nama penulis, tahun, kata dari kalimat, atau nomor subbab. */
export function LedgerList({ entries }: { entries: LedgerEntry[] }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "cited" | "uncited">("all");

  const index = useMemo(() => entries.map((e) => ({ e, h: haystack(e) })), [entries]);
  const terms = fold(q).split(/\s+/).filter(Boolean);
  const shown = index.filter(({ e, h }) => (filter === "all" || e.status === filter) && terms.every((t) => h.includes(t))).map((x) => x.e);

  return (
    <div className="mt-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-black/35" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari penulis, tahun, kata dari kalimat, atau nomor subbab…" className="pl-9" aria-label="Cari rujukan" />
        </div>
        <div className="inline-flex rounded-btn bg-black/5 p-0.5 text-[12px] font-medium" role="group" aria-label="Filter status">
          {(["all", "cited", "uncited"] as const).map((f) => (
            <button key={f} type="button" onClick={() => setFilter(f)} className={cn("rounded-btn px-3 py-2.5 transition-colors sm:py-1.5", filter === f ? "bg-white shadow-sm" : "text-black/55")}>
              {f === "all" ? "Semua" : f === "cited" ? "Dikutip" : "Belum dikutip"}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 text-[12px] text-black/50" aria-live="polite">
        {shown.length} dari {entries.length} rujukan
      </p>

      <ul className="mt-2 divide-y divide-hairline rounded-btn border border-hairline">
        {shown.length === 0 && <li className="p-4 text-[13px] text-black/55">Tidak ada rujukan yang cocok dengan pencarian.</li>}
        {shown.map((e) => {
          const isOpen = open === e.citation_id;
          return (
            <li key={e.citation_id}>
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : e.citation_id)}
                aria-expanded={isOpen}
                className="flex w-full items-start gap-3 p-3 text-left transition-colors hover:bg-black/[0.02] active:bg-black/[0.04]"
              >
                <span className="mt-0.5 w-6 shrink-0 text-[12px] tabular-nums text-black/40">{e.number}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-ink">{e.short}</span>
                  <span className="mt-0.5 line-clamp-2 block text-[12px] text-black/60">{e.title}</span>
                </span>
                {e.status === "cited" ? <Pill tone="green">{e.uses.length}× dikutip</Pill> : <Pill tone="yellow">belum dikutip</Pill>}
                <ChevronDown size={15} className={cn("mt-1 shrink-0 text-black/40 transition-transform", isOpen && "rotate-180")} />
              </button>
              {isOpen && (
                <div className="space-y-3 border-t border-hairline bg-black/[0.015] p-3 text-[13px]">
                  <p className="leading-relaxed text-black/80">{e.reference}</p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-black/55">
                    {e.source && <span>Sumber data: {e.source}</span>}
                    {e.doi_url && (
                      <a className="inline-flex items-center gap-1 text-brand underline-offset-2 hover:underline" href={e.doi_url} target="_blank" rel="noreferrer">
                        DOI <ExternalLink size={11} />
                      </a>
                    )}
                    {e.pdf_url && (
                      <a className="inline-flex items-center gap-1 text-brand underline-offset-2 hover:underline" href={e.pdf_url} target="_blank" rel="noreferrer">
                        PDF <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                  <div>
                    <p className="text-[12px] font-semibold uppercase tracking-wide text-black/45">Bukti grounding</p>
                    <p className="mt-1 rounded-btn border border-hairline bg-white p-2.5 italic leading-relaxed text-black/75">{e.evidence ? `“${e.evidence}”` : "Tidak ada cuplikan tersimpan untuk rujukan ini."}</p>
                  </div>
                  <div>
                    <p className="text-[12px] font-semibold uppercase tracking-wide text-black/45">Dikutip di</p>
                    {e.uses.length === 0 && <p className="mt-1 text-black/55">Belum ada kutipan di naskah.</p>}
                    <ul className="mt-1 space-y-2">
                      {e.uses.map((u, i) => (
                        <li key={i} className="border-l-2 border-hairline pl-3">
                          <p className="text-[12px] font-medium text-black/70">{where(u.section, u.title)}</p>
                          <p className="leading-relaxed text-black/80">{u.sentence}</p>
                          {u.year_mismatch && <p className="text-[12px] text-vermillion">Tahun di naskah ({u.marker}) berbeda dengan rujukan ({e.year}).</p>}
                          {u.grounded_snippet && u.grounded_snippet !== e.evidence && <p className="mt-0.5 text-[12px] italic text-black/55">Bukti yang dipakai penulis agen: “{u.grounded_snippet}”</p>}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
