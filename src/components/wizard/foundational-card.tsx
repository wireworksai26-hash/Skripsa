"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api, type FoundationalResult } from "@/lib/api";
import { useProject } from "@/lib/store";
import { BookMarked, CheckCircle2, CircleSlash } from "lucide-react";
import { useState } from "react";

const MAX_SELECTED = 15;

/** Mencocokkan daftar di isian Teori (Mode lanjutan) ke basis data publik. Hanya karya yang benar-benar ditemukan yang masuk. */
export function FoundationalCard() {
  const project = useProject((s) => s.project);
  const setPart = useProject((s) => s.setPart);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<FoundationalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!project) return null;

  const theory = project.brief.theory.trim();
  const lines = theory ? theory.split(/\r?\n/).filter((l) => l.trim()).length : 0;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.foundationalRefs(project.id);
      const fresh = await api.loadThesis(project.id);
      // Teori dasar dipilih lebih dulu agar tidak tergeser pilihan lain oleh batas 15 rujukan.
      const ids = r.found.map((f) => f.citation_id);
      const selected = [...ids, ...project.selectedRefIds.filter((id) => !ids.includes(id))].slice(0, MAX_SELECTED);
      await api.setSelectedRefs(project.id, selected);
      setPart({ references: fresh.references, selectedRefIds: selected });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal mencocokkan teori");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <Pill tone="blue">
        <BookMarked size={12} /> Dari isian Teori Anda
      </Pill>
      <h2 className="t-heading-sm mt-3">Teori dasar</h2>
      {theory ? (
        <p className="mt-1 text-[13px] leading-relaxed text-graphite">
          Mencocokkan {lines} baris di isian Teori ke OpenAlex dan Crossref, tanpa batas tahun. Hanya karya yang benar-benar ditemukan
          (judul, penulis pertama, dan tahun cocok) yang dimasukkan dan dipilih. Yang tidak ketemu dilaporkan, tidak dikarang.
        </p>
      ) : (
        <p className="mt-1 text-[13px] leading-relaxed text-graphite">
          Isian Teori di Langkah 1 (Mode lanjutan) masih kosong. Tulis rujukan teori Anda satu per baris, contoh:{" "}
          <span className="font-mono text-[12px]">Bandura, A. (1997). Self-Efficacy: The Exercise of Control.</span>
        </p>
      )}
      <div className="mt-4">
        <Button variant="ghost" loading={busy} disabled={busy || !theory} onClick={run}>
          {!busy && <BookMarked size={15} />} {result ? "Cocokkan ulang" : "Cari teori saya"}
        </Button>
      </div>
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}

      {result && (
        <div className="mt-4 space-y-4 text-[13px]">
          <p className="text-black/70">
            {result.found.length} ditemukan ({result.added} baru), {result.not_found.length + result.unparsed.length} belum.
            {result.found.length > 0 && " Yang ditemukan sudah dipilih di daftar di bawah."}
          </p>

          {result.found.length > 0 && (
            <ul className="space-y-2">
              {result.found.map((f) => (
                <li key={f.citation_id} className="flex gap-2">
                  <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-[#0a5f1e]" />
                  <div className="min-w-0">
                    <p className="font-medium text-black/85">{f.title}</p>
                    <p className="text-black/60">
                      {f.authors.slice(0, 3).join(", ")} · {f.publication_year}
                      {f.doi ? ` · DOI ${f.doi}` : ""}
                    </p>
                    {!f.highlighted_snippet && (
                      <p className="text-black/55">Tanpa abstrak di basis data: masuk daftar pustaka, tetapi tidak bisa dikutip kata per kata.</p>
                    )}
                    {f.note && <p className="text-saffron">{f.note}</p>}
                  </div>
                </li>
              ))}
            </ul>
          )}

          {(result.not_found.length > 0 || result.unparsed.length > 0) && (
            <ul className="space-y-2">
              {result.not_found.map((n) => (
                <li key={n.raw} className="flex gap-2">
                  <CircleSlash size={15} className="mt-0.5 shrink-0 text-vermillion" />
                  <div className="min-w-0">
                    <p className="font-medium text-black/85">{n.raw}</p>
                    <p className="text-black/60">{n.reason}</p>
                    {n.closest && (
                      <p className="text-black/55">
                        Terdekat: {n.closest.title} ({n.closest.year ?? "?"}){n.closest.doi ? `, DOI ${n.closest.doi}` : ""}
                      </p>
                    )}
                  </div>
                </li>
              ))}
              {result.unparsed.map((n) => (
                <li key={n.raw} className="flex gap-2">
                  <CircleSlash size={15} className="mt-0.5 shrink-0 text-black/40" />
                  <div className="min-w-0">
                    <p className="font-medium text-black/85">{n.raw}</p>
                    <p className="text-black/60">{n.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}
