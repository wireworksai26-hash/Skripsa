"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { SimilarityReport } from "@/lib/types";
import { ScanSearch } from "lucide-react";
import { useState } from "react";

/** Pemeriksa kemiripan internal: draf dibandingkan dengan judul + abstrak rujukan proyek ini (bukan pengganti Turnitin). */
export function SimilarityCard() {
  const project = useProject((s) => s.project);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<SimilarityReport | null>(null);
  if (!project) return null;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setReport(await api.similarity(project.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal memeriksa");
    } finally {
      setBusy(false);
    }
  };
  const flagged = report?.sections.filter((s) => s.flagged.length > 0) ?? [];

  return (
    <Card>
      <Pill tone="blue">
        <ScanSearch size={12} /> Kemiripan
      </Pill>
      <h2 className="t-heading-sm mt-3">Cek kemiripan dengan rujukan</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Menandai paragraf yang hampir sama persis dengan abstrak rujukan Anda (tanpa tanda kutip). Ini pemeriksaan awal terhadap rujukan di proyek ini; tetap gunakan alat resmi kampus untuk hasil akhir.
      </p>
      <Button className="mt-4" onClick={run} loading={busy}>
        {!busy && <ScanSearch size={15} />} Periksa sekarang
      </Button>
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}
      {report && (
        <div className="mt-4 space-y-3 text-[13px]">
          <p className="text-black/60">
            Dibandingkan dengan {report.sourcesCompared} rujukan. Kemiripan tertinggi {Math.round(report.overallPeak * 100)}% (batas tanda {Math.round(report.threshold * 100)}%).
          </p>
          {flagged.length === 0 ? (
            <p className="rounded-btn bg-[#f0faf0] p-3 text-[#0a4d1e]">Tidak ada paragraf yang menyalin abstrak rujukan.</p>
          ) : (
            flagged.map((s) => (
              <div key={s.code} className="rounded-btn border border-vermillion/30 bg-vermillion/5 p-3">
                <p className="font-semibold text-vermillion">
                  {s.code} {s.title}
                </p>
                {s.flagged.map((f, i) => (
                  <p key={i} className="mt-1.5 text-black/75">
                    “{f.excerpt}…” <span className="text-black/45">· {Math.round(f.score * 100)}% mirip dengan {f.source}</span>
                  </p>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </Card>
  );
}
