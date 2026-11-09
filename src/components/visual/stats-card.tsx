"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldHint, Input, Label, Select, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { fmtId, fmtP, parseGroupsCsv, type GroupData } from "@/lib/stats-csv";
import { useProject } from "@/lib/store";
import type { StatsResult } from "@/lib/types";
import { FileSpreadsheet, FlaskConical, Loader2 } from "lucide-react";
import { useRef, useState } from "react";

export function StatsCard() {
  const addTable = useProject((s) => s.addTable);
  const addChart = useProject((s) => s.addChart);

  const fileRef = useRef<HTMLInputElement>(null);
  const [raw, setRaw] = useState("");
  const [groups, setGroups] = useState<GroupData[] | null>(null);
  const [format, setFormat] = useState<string>("");
  const [title, setTitle] = useState("");
  const [paired, setPaired] = useState(false);
  const [alpha, setAlpha] = useState("0.05");
  const [result, setResult] = useState<StatsResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const read = (text: string) => {
    setRaw(text);
    setResult(null);
    setMessage(null);
    const parsed = parseGroupsCsv(text);
    if (!parsed.ok) {
      setGroups(null);
      setMessage({ kind: "error", text: parsed.error });
      return;
    }
    setGroups(parsed.groups);
    setFormat(parsed.format);
    if (parsed.skipped > 0) setMessage({ kind: "ok", text: `${parsed.skipped} sel non-numerik dilewati.` });
  };

  const analyze = async () => {
    if (!groups) return;
    setBusy(true);
    setMessage(null);
    try {
      setResult(await api.analyzeStats(groups, paired && groups.length === 2, Number(alpha)));
    } catch (e) {
      setResult(null);
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Analisis gagal" });
    } finally {
      setBusy(false);
    }
  };

  const saveTables = async () => {
    if (!result || !title.trim()) return;
    setBusy(true);
    setMessage(null);
    try {
      await addTable({
        title: `Statistik deskriptif ${title.trim()}`,
        caption: `Statistik deskriptif ${title.trim()}`,
        columns: ["Kelompok", "n", "Rerata", "SD", "Min", "Maks"],
        rows: result.descriptives.map((d) => [d.group, String(d.n), fmtId(d.mean), fmtId(d.sd), fmtId(d.min), fmtId(d.max)]),
        note: "",
      });
      const t = result.test;
      if (t) {
        await addTable({
          title: `Hasil ${t.name.toLowerCase()} ${title.trim()}`,
          caption: `Hasil ${t.name.toLowerCase()} ${title.trim()}`,
          columns: ["Uji", "Statistik", "db", "p", t.effect_name, "Keputusan"],
          rows: [
            [
              t.name,
              fmtId(t.statistic),
              t.df2 !== undefined ? `${t.df}, ${t.df2}` : fmtId(t.df, Number.isInteger(t.df) ? 0 : 1),
              fmtP(t.p),
              t.effect_size === null ? "-" : fmtId(t.effect_size),
              t.significant ? `Signifikan (α = ${fmtId(result.alpha)})` : `Tidak signifikan (α = ${fmtId(result.alpha)})`,
            ],
          ],
          note: result.interpretation,
        });
      }
      setMessage({ kind: "ok", text: `Tabel disimpan dan akan masuk ke Bab IV${t ? " (deskriptif + hasil uji)" : ""}.` });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Tabel tidak tersimpan" });
    } finally {
      setBusy(false);
    }
  };

  const saveChart = async () => {
    if (!result || !title.trim()) return;
    setBusy(true);
    setMessage(null);
    try {
      await addChart({
        kind: "bar",
        title: `Rerata ${title.trim()}`,
        ylabel: "Rerata",
        series: result.descriptives.map((d) => ({ label: d.group, value: Number(d.mean.toFixed(2)) })),
        caption: `Rerata ${title.trim()}`,
      });
      setMessage({ kind: "ok", text: "Grafik rerata ditambahkan ke Bab IV." });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Grafik tidak tersimpan" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="sky">
          <FlaskConical size={12} /> Modul kuantitatif
        </Pill>
        <Pill>Rerata · SD · uji t · ANOVA</Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Uji statistik dari data mentah</h2>
      <p className="mt-1 text-[13px] text-graphite">
        Unggah CSV/TSV dari Excel: format panjang (kolom kelompok dan nilai) atau lebar (satu kolom per kelompok, mis. Pre dan Post).
        Dua kelompok memakai uji t (Welch, atau berpasangan), tiga kelompok atau lebih memakai ANOVA satu arah.
      </p>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="rawdata">Data</Label>
            <Button variant="text" size="sm" onClick={() => fileRef.current?.click()}>
              <FileSpreadsheet size={14} /> Pilih berkas CSV
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.tsv,.txt,text/csv"
              className="hidden"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (f) read(await f.text());
                e.target.value = "";
              }}
            />
          </div>
          <Textarea
            id="rawdata"
            value={raw}
            onChange={(e) => read(e.target.value)}
            rows={7}
            className="font-mono text-[13px]"
            placeholder={"Kelompok,Skor\nKontrol,60\nKontrol,62\nEksperimen,75\nEksperimen,78"}
          />
          {groups && (
            <FieldHint>
              Terbaca {groups.length} kelompok (format {format}): {groups.map((g) => `${g.name} n=${g.values.length}`).join(" · ")}
            </FieldHint>
          )}
        </div>

        <div className="space-y-3">
          <div>
            <Label htmlFor="stitle">Judul hasil</Label>
            <Input id="stitle" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="motivasi belajar kelas kontrol dan eksperimen" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="alpha">Taraf signifikansi</Label>
              <Select id="alpha" value={alpha} onChange={(e) => setAlpha(e.target.value)}>
                <option value="0.05">α = 0,05</option>
                <option value="0.01">α = 0,01</option>
                <option value="0.1">α = 0,10</option>
              </Select>
            </div>
            <label className="mt-6 flex items-center gap-2 text-[13px] text-black/70">
              <input
                type="checkbox"
                checked={paired}
                disabled={!groups || groups.length !== 2}
                onChange={(e) => setPaired(e.target.checked)}
              />
              Berpasangan (pre-post)
            </label>
          </div>
          <Button variant="primary" onClick={analyze} disabled={!groups || busy}>
            {busy ? <Loader2 size={15} className="animate-spin" /> : <FlaskConical size={15} />} Hitung
          </Button>
        </div>
      </div>

      {message && <p className={`mt-3 text-[13px] ${message.kind === "error" ? "text-vermillion" : "text-graphite"}`}>{message.text}</p>}

      {result && (
        <div className="mt-5 space-y-4">
          <div className="scroll-thin overflow-x-auto rounded-btn border border-hairline">
            <table className="w-full min-w-[480px] text-left text-[13px]">
              <thead className="bg-canvas text-black/55">
                <tr>
                  {["Kelompok", "n", "Rerata", "SD", "Min", "Maks"].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.descriptives.map((d) => (
                  <tr key={d.group} className="border-t border-hairline">
                    <td className="px-3 py-2 font-medium">{d.group}</td>
                    <td className="px-3 py-2">{d.n}</td>
                    <td className="px-3 py-2">{fmtId(d.mean)}</td>
                    <td className="px-3 py-2">{fmtId(d.sd)}</td>
                    <td className="px-3 py-2">{fmtId(d.min)}</td>
                    <td className="px-3 py-2">{fmtId(d.max)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.test && (
            <div className={`rounded-btn border p-3 text-[13px] ${result.test.significant ? "border-[#8ed78c]/60 bg-[#f0faf0]" : "border-hairline bg-canvas"}`}>
              <p className="font-semibold">
                {result.test.name}: {result.test.report}
              </p>
            </div>
          )}
          <p className="text-[13.5px] leading-relaxed text-charcoal">{result.interpretation}</p>

          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={saveTables} disabled={busy || !title.trim()}>
              Simpan tabel ke Bab IV
            </Button>
            <Button variant="ghost" onClick={saveChart} disabled={busy || !title.trim()}>
              Buat grafik rerata
            </Button>
            {!title.trim() && <span className="self-center text-[12px] text-black/45">Isi judul hasil dulu.</span>}
          </div>
        </div>
      )}
    </Card>
  );
}
