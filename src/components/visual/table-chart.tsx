"use client";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { useProject } from "@/lib/store";
import type { ResultTable } from "@/lib/types";
import { parseLocaleNumber } from "@/lib/visuals";
import { BarChart3 } from "lucide-react";
import { useMemo, useState } from "react";

/** Ubah kolom numerik sebuah tabel tersimpan menjadi grafik (data nyata dari tabel; sel [DATA] dilewati). */
export function TableChart({ table, onError }: { table: ResultTable; onError: (e: unknown) => void }) {
  const addChart = useProject((s) => s.addChart);
  const numeric = useMemo(
    () => table.columns.map((c, i) => ({ c, i })).filter(({ i }) => i > 0 && table.rows.filter((r) => parseLocaleNumber(r[i] ?? "") !== null).length >= 2),
    [table]
  );
  const [col, setCol] = useState<number | null>(null);
  const [kind, setKind] = useState<"bar" | "line" | "pie">("bar");
  const [done, setDone] = useState(false);
  if (numeric.length === 0) return null;
  const current = col ?? numeric[0].i;

  const make = () => {
    const series = table.rows
      .map((r) => ({ label: r[0] ?? "", value: parseLocaleNumber(r[current] ?? "") }))
      .filter((s): s is { label: string; value: number } => s.value !== null && s.label.trim() !== "");
    const name = table.columns[current];
    addChart({
      kind,
      title: `${name} — ${table.title}`.slice(0, 120),
      ylabel: name,
      series,
      caption: `${name} — ${table.caption || table.title}`.slice(0, 160),
      chapter: table.chapter ?? "4",
    })
      .then(() => setDone(true))
      .catch(onError);
  };

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-dashed border-hairline pt-2 text-[12.5px] text-black/60">
      <BarChart3 size={14} />
      <span>Buat grafik dari kolom</span>
      <Select aria-label="Kolom data" className="!w-auto !py-2 sm:!py-1" value={current} onChange={(e) => (setCol(Number(e.target.value)), setDone(false))}>
        {numeric.map(({ c, i }) => (
          <option key={i} value={i}>
            {c}
          </option>
        ))}
      </Select>
      <Select aria-label="Jenis grafik" className="!w-auto !py-2 sm:!py-1" value={kind} onChange={(e) => (setKind(e.target.value as typeof kind), setDone(false))}>
        <option value="bar">Batang</option>
        <option value="line">Garis</option>
        <option value="pie">Lingkaran</option>
      </Select>
      <Button variant="ghost" size="sm" onClick={make}>
        Buat grafik
      </Button>
      {done && <span className="text-brand">Grafik ditambahkan.</span>}
    </div>
  );
}
