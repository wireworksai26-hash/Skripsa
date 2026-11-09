"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldHint, Input, Label, Select } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { BarChart, LineChart, PieChart } from "@/components/charts/charts";
import { useProject } from "@/lib/store";
import type { ChartSeries, ChartSpec } from "@/lib/types";
import { DiagramCard } from "@/components/visual/diagram-card";
import { StatsCard } from "@/components/visual/stats-card";
import { ResearchDataCard } from "@/components/visual/research-data-card";
import { VisualPlannerCard } from "@/components/visual/planner-card";
import { TableChart } from "@/components/visual/table-chart";
import { parseSeriesCsv, seriesStats } from "@/lib/visuals";
import { ChartNetwork, FileSpreadsheet, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

type Kind = "bar" | "line" | "pie";

const BLANK_ROW: ChartSeries = { label: "", value: 0 };

const fmt = (n: number) => new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 }).format(n);

export default function VisualPage() {
  const project = useProject((s) => s.project);
  const addChart = useProject((s) => s.addChart);
  const removeChart = useProject((s) => s.removeChart);
  const removeTable = useProject((s) => s.removeTable);
  const removeDiagram = useProject((s) => s.removeDiagram);

  const [kind, setKind] = useState<Kind>("bar");
  const [title, setTitle] = useState("");
  const [xlabel, setXlabel] = useState("");
  const [ylabel, setYlabel] = useState("");
  const [rows, setRows] = useState<ChartSeries[]>([{ ...BLANK_ROW }]);
  const [csvMsg, setCsvMsg] = useState<string | null>(null);
  const [chartChapter, setChartChapter] = useState("4");
  const fileRef = useRef<HTMLInputElement>(null);

  const [actionErr, setActionErr] = useState<string | null>(null);

  if (!project) return null;
  const isTeknik = project.form.domain === "INFORMATIKA";
  const stats = seriesStats(rows);
  const validRows = rows.filter((r) => r.label.trim());

  const setRow = (i: number, field: "label" | "value", v: string) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, [field]: field === "value" ? Number(v) || 0 : v } : r)));

  const importCsv = async (file: File) => {
    const parsed = parseSeriesCsv(await file.text());
    if (parsed.length === 0) {
      setCsvMsg("Tidak ada baris data terbaca. Pakai dua kolom: label dan nilai.");
      return;
    }
    setRows(parsed.slice(0, 30));
    setCsvMsg(`${Math.min(parsed.length, 30)} baris dari ${file.name} dimuat${parsed.length > 30 ? " (dibatasi 30 baris)" : ""}.`);
  };

  const report = (e: unknown) => setActionErr(e instanceof Error ? e.message : "Aksi gagal");

  const submitChart = () => {
    setActionErr(null);
    const spec: Omit<ChartSpec, "id"> = {
      kind,
      title: title.trim() || "Grafik",
      xlabel: xlabel || undefined,
      ylabel: ylabel || undefined,
      series: validRows,
      caption: title.trim() || "Grafik",
      chapter: chartChapter,
    };
    addChart(spec)
      .then(() => {
        setTitle("");
        setXlabel("");
        setYlabel("");
        setRows([{ ...BLANK_ROW }]);
      })
      .catch(report);
  };

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="coral">
            <ChartNetwork size={12} /> Visualizer Engine
          </Pill>
          {isTeknik && <Pill tone="blue">Domain Teknik: diagram UML tersedia</Pill>}
          <Pill>
            {project.tables.length} tabel · {project.charts.length} grafik · {project.diagrams.length} diagram tersimpan; nomor Gambar/Tabel mengikuti bab tujuannya saat ekspor
          </Pill>
        </div>
        <h1 className="t-heading mt-4">Tabel, grafik &amp; diagram per bab</h1>
        <p className="t-serif-lede mt-2 text-graphite">
          Minta saran AI untuk tiap bab, hitung uji statistik dari data mentah, atau buat sendiri. Semuanya disisipkan
          otomatis di bab tujuannya sebagai tabel dan gambar bernomor saat ekspor .docx.
        </p>
      </Card>

      {actionErr && <p className="text-[13px] text-vermillion">{actionErr}</p>}

      <ResearchDataCard />

      <VisualPlannerCard />

      <StatsCard />

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <Card>
          <h2 className="t-heading-sm flex items-center gap-2">
            <SlidersHorizontal size={16} /> Grafik baru
          </h2>
          <div className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="kind">Tipe</Label>
                <Select id="kind" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
                  <option value="bar">Batang</option>
                  <option value="line">Garis</option>
                  <option value="pie">Lingkaran</option>
                </Select>
              </div>
              <div>
                <Label htmlFor="ctitle">Judul grafik</Label>
                <Input id="ctitle" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Skor motivasi per kelompok" />
              </div>
            </div>
            <div>
              <Label htmlFor="cchapter">Disisipkan di</Label>
              <Select id="cchapter" value={chartChapter} onChange={(e) => setChartChapter(e.target.value)}>
                {project.template.chapters.map((c) => (
                  <option key={c.chapter_number} value={c.chapter_number}>
                    BAB {c.chapter_number} · {c.chapter_title}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="cx">Label sumbu X</Label>
                <Input id="cx" value={xlabel} onChange={(e) => setXlabel(e.target.value)} placeholder="Kelas praktik" />
              </div>
              <div>
                <Label htmlFor="cy">Label sumbu Y</Label>
                <Input id="cy" value={ylabel} onChange={(e) => setYlabel(e.target.value)} placeholder="Skor motivasi" />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label>Deret data</Label>
                <Button variant="text" size="sm" onClick={() => fileRef.current?.click()}>
                  <FileSpreadsheet size={14} /> Impor CSV
                </Button>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.tsv,.txt,text/csv"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void importCsv(f);
                    e.target.value = "";
                  }}
                />
              </div>
              <div className="space-y-2">
                {rows.map((row, i) => (
                  <div key={i} className="flex gap-2">
                    <Input value={row.label} onChange={(e) => setRow(i, "label", e.target.value)} placeholder="Label" aria-label={`Label baris ${i + 1}`} />
                    <Input
                      type="number"
                      value={row.value}
                      onChange={(e) => setRow(i, "value", e.target.value)}
                      className="w-24"
                      placeholder="Nilai"
                      aria-label={`Nilai baris ${i + 1}`}
                    />
                    <Button variant="text" size="sm" onClick={() => setRows((r) => r.filter((_, idx) => idx !== i))} aria-label="Hapus baris">
                      <Trash2 size={14} />
                    </Button>
                  </div>
                ))}
              </div>
              <Button variant="text" size="sm" className="mt-2" onClick={() => setRows((r) => [...r, { ...BLANK_ROW }])}>
                <Plus size={14} /> Tambah baris
              </Button>
              {csvMsg && <FieldHint>{csvMsg}</FieldHint>}
              {stats && (
                <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 rounded-btn border border-hairline bg-canvas p-2 text-center text-[12px]">
                  {[
                    ["n", String(stats.n)],
                    ["Mean", fmt(stats.mean)],
                    ["SD", fmt(stats.sd)],
                    ["Rentang", `${fmt(stats.min)}–${fmt(stats.max)}`],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-black/45">{k}</dt>
                      <dd className="font-semibold text-black/85">{v}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            <Button variant="primary" className="w-full" onClick={submitChart} disabled={validRows.length === 0 || !title.trim()}>
              Tambahkan ke Bab IV
            </Button>
            <FieldHint>Uji lanjutan (t-test, ANOVA) belum dihitung di sisi klien; masukkan hasilnya sebagai deret data.</FieldHint>
          </div>
        </Card>

        <div className="space-y-4">
          {project.charts.length === 0 && (
            <Card className="border-dashed text-center text-[13px] text-black/50">
              Belum ada grafik pada proyek ini. Isi formulir di kiri, lalu tekan tambahkan.
            </Card>
          )}
          {project.charts.map((c) => {
            const s = seriesStats(c.series);
            return (
              <Card key={c.id}>
                <div className="flex items-center justify-between gap-3">
                  <h3 className="t-heading-sm">
                    BAB {c.chapter ?? "4"} · {c.title}
                  </h3>
                  <Button variant="text" size="sm" onClick={() => removeChart(c.id).catch(report)} aria-label={`Hapus grafik ${c.title}`}>
                    <Trash2 size={15} />
                  </Button>
                </div>
                <div className="mt-3 rounded-btn bg-white p-3">
                  {c.kind === "bar" && <BarChart series={c.series} xlabel={c.xlabel} ylabel={c.ylabel} />}
                  {c.kind === "line" && <LineChart series={c.series} xlabel={c.xlabel} ylabel={c.ylabel} />}
                  {c.kind === "pie" && <PieChart series={c.series} />}
                </div>
                {s && (
                  <p className="mt-2 text-[12px] text-black/45">
                    n = {s.n} · mean = {fmt(s.mean)} · SD = {fmt(s.sd)}
                  </p>
                )}
              </Card>
            );
          })}
        </div>
      </div>

      <DiagramCard />

      {project.tables.length > 0 && (
        <Card>
          <h2 className="t-heading-sm">Tabel tersimpan</h2>
          <ul className="mt-3 space-y-4">
            {project.tables.map((t) => (
              <li key={t.id} className="rounded-btn border border-hairline p-3">
                <div className="flex items-center justify-between gap-3 text-[13px]">
                  <span className="font-semibold">
                    Tabel · BAB {t.chapter ?? "4"} · {t.title}
                  </span>
                  <Button variant="text" size="sm" onClick={() => removeTable(t.id).catch(report)} aria-label={`Hapus tabel ${t.title}`}>
                    <Trash2 size={14} />
                  </Button>
                </div>
                <div className="scroll-thin mt-2 overflow-x-auto">
                  <table className="w-full min-w-[420px] text-left text-[12.5px]">
                    <thead className="text-black/50">
                      <tr>
                        {t.columns.map((c) => (
                          <th key={c} className="px-2 py-1 font-medium">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {t.rows.map((r, ri) => (
                        <tr key={ri} className="border-t border-hairline">
                          {r.map((c, ci) => (
                            <td key={ci} className="px-2 py-1">
                              {c}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {t.note && <p className="mt-2 text-[12px] leading-relaxed text-black/55">{t.note}</p>}
                <TableChart table={t} onError={report} />
              </li>
            ))}
          </ul>
        </Card>
      )}

      {project.diagrams.length > 0 && (
        <Card>
          <h2 className="t-heading-sm">Diagram tersimpan</h2>
          <ul className="mt-3 space-y-4">
            {project.diagrams.map((d) => (
              <li key={d.id} className="rounded-btn border border-hairline p-3">
                <div className="flex items-center justify-between gap-3 text-[13px]">
                  <span className="font-semibold">
                    BAB {d.chapter ?? "4"} · {d.title}
                  </span>
                  <Button variant="text" size="sm" onClick={() => removeDiagram(d.id).catch(report)} aria-label={`Hapus diagram ${d.title}`}>
                    <Trash2 size={14} />
                  </Button>
                </div>
                {d.image ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img src={d.image} alt={d.title} className="mt-2 max-h-72 rounded-btn bg-white p-2" />
                ) : (
                  <p className="mt-2 text-[12px] text-vermillion">
                    Diagram lama tanpa gambar — hapus lalu simpan ulang agar ikut terekspor.
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
