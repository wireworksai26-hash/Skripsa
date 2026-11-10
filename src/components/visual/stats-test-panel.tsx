"use client";

import { Button } from "@/components/ui/button";
import { Label, Select } from "@/components/ui/field";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { DataColumn, StatTestKind, StatTestResult } from "@/lib/types";
import { FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";

const KINDS: Array<[StatTestKind, string, string]> = [
  ["correlation", "Korelasi (Pearson + Spearman)", "Dua variabel angka."],
  ["regression", "Regresi linear (sederhana atau berganda)", "Satu variabel terikat (Y) dan satu atau lebih variabel bebas (X)."],
  ["chi_square", "Chi-square independensi", "Dua variabel kategori (maks. 10 kategori)."],
  ["normality", "Uji normalitas (Shapiro-Wilk)", "Satu variabel angka."],
  ["reliability", "Reliabilitas instrumen (Cronbach's alpha)", "Dua atau lebih butir kuesioner (kolom angka)."],
];

/** Uji statistik pada kumpulan data bertipe tabel. Semua dihitung langsung (numpy/scipy), bukan oleh LLM. */
export function StatsTestPanel({ dataId, onDone }: { dataId: string; onDone: () => Promise<void> | void }) {
  const project = useProject((s) => s.project);
  const reload = useProject((s) => s.reload);
  const [cols, setCols] = useState<DataColumn[] | null>(null);
  const [kind, setKind] = useState<StatTestKind>("correlation");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [y, setY] = useState("");
  const [multi, setMulti] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StatTestResult | null>(null);
  const id = project?.id;

  useEffect(() => {
    if (id) api.dataColumns(id, dataId).then(setCols).catch((e) => setError(e instanceof Error ? e.message : "Gagal memuat kolom"));
  }, [id, dataId]);

  if (!project || !id) return null;
  const nums = (cols ?? []).filter((c) => c.numeric);
  const cats = (cols ?? []).filter((c) => !c.numeric || c.distinct <= 10);
  const toggle = (n: string) => setMulti((m) => (m.includes(n) ? m.filter((x) => x !== n) : [...m, n]));

  const ready =
    (kind === "correlation" && a && b && a !== b) ||
    (kind === "regression" && y && multi.filter((x) => x !== y).length >= 1) ||
    (kind === "chi_square" && a && b && a !== b) ||
    (kind === "normality" && a) ||
    (kind === "reliability" && multi.length >= 2);

  const run = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.runStatTest(id, dataId, {
        kind,
        a: a || undefined,
        b: b || undefined,
        y: y || undefined,
        xs: kind === "regression" ? multi.filter((x) => x !== y) : [],
        items: kind === "reliability" ? multi : [],
        column: kind === "normality" ? a : undefined,
      });
      setResult(r);
      await Promise.all([reload(), onDone()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Uji gagal");
    } finally {
      setBusy(false);
    }
  };

  const colSelect = (label: string, value: string, set: (v: string) => void, list: DataColumn[], idp: string) => (
    <div>
      <Label htmlFor={`${idp}-${dataId}`}>{label}</Label>
      <Select id={`${idp}-${dataId}`} value={value} onChange={(e) => set(e.target.value)}>
        <option value="">Pilih kolom…</option>
        {list.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name}
          </option>
        ))}
      </Select>
    </div>
  );

  return (
    <div className="mt-3 rounded-card border border-dashed border-hairline-strong p-3">
      <p className="flex items-center gap-1.5 text-[13px] font-semibold">
        <FlaskConical size={14} /> Uji statistik
      </p>
      <div className="mt-2 grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Label htmlFor={`kind-${dataId}`}>Jenis uji</Label>
          <Select id={`kind-${dataId}`} value={kind} onChange={(e) => (setKind(e.target.value as StatTestKind), setResult(null), setMulti([]))}>
            {KINDS.map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </Select>
          <p className="mt-1 text-[12px] text-black/50">{KINDS.find((k) => k[0] === kind)?.[2]}</p>
        </div>
        {kind === "correlation" && (
          <>
            {colSelect("Variabel 1", a, setA, nums, "a")}
            {colSelect("Variabel 2", b, setB, nums, "b")}
          </>
        )}
        {kind === "chi_square" && (
          <>
            {colSelect("Variabel kategori 1", a, setA, cats, "a")}
            {colSelect("Variabel kategori 2", b, setB, cats, "b")}
          </>
        )}
        {kind === "normality" && colSelect("Variabel", a, setA, nums, "a")}
        {kind === "regression" && (
          <>
            {colSelect("Variabel terikat (Y)", y, setY, nums, "y")}
            <fieldset>
              <legend className="mb-1.5 text-sm font-medium">Variabel bebas (X)</legend>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {nums
                  .filter((c) => c.name !== y)
                  .map((c) => (
                    <label key={c.name} className="inline-flex min-h-9 cursor-pointer items-center gap-1.5 text-[13.5px]">
                      <input type="checkbox" checked={multi.includes(c.name)} onChange={() => toggle(c.name)} /> {c.name}
                    </label>
                  ))}
              </div>
            </fieldset>
          </>
        )}
        {kind === "reliability" && (
          <fieldset className="sm:col-span-2">
            <legend className="mb-1.5 text-sm font-medium">Butir instrumen</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {nums.map((c) => (
                <label key={c.name} className="inline-flex min-h-9 cursor-pointer items-center gap-1.5 text-[13.5px]">
                  <input type="checkbox" checked={multi.includes(c.name)} onChange={() => toggle(c.name)} /> {c.name}
                </label>
              ))}
            </div>
          </fieldset>
        )}
      </div>
      <Button className="mt-3" size="sm" onClick={run} loading={busy} disabled={busy || !ready}>
        {!busy && <FlaskConical size={14} />} Jalankan uji
      </Button>
      {error && <p className="mt-2 text-[13px] text-vermillion">{error}</p>}
      {result && (
        <div className="mt-3 space-y-1 text-[13px]">
          <p className="font-medium">{result.report}</p>
          <p className="text-black/70">{result.interpretation}</p>
          <p className="text-[12px] text-black/45">Tabel hasil masuk ke Bab IV. Buat ulang subbab hasil/pembahasan di Langkah 4 agar penulis memakainya.</p>
        </div>
      )}
    </div>
  );
}
