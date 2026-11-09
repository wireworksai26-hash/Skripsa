"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { VisualProposal } from "@/lib/types";
import { renderDiagramPng, type RasterImage } from "@/lib/visuals";
import { cn } from "@/lib/utils";
import { AlertTriangle, Check, Image as ImageIcon, Loader2, Sparkles } from "lucide-react";
import { Fragment, useState } from "react";

/** Sorot penanda [DATA: …] agar jelas bagian yang wajib diisi dari penelitian sebenarnya. */
function Cell({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[DATA:[^\]]*\])/i).map((part, i) =>
        /^\[DATA:/i.test(part) ? (
          <span key={i} className="rounded-[3px] bg-marigold/40 px-0.5">
            {part}
          </span>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        )
      )}
    </>
  );
}

export function VisualPlannerCard() {
  const project = useProject((s) => s.project);
  const addTable = useProject((s) => s.addTable);
  const addDiagram = useProject((s) => s.addDiagram);

  const [chapter, setChapter] = useState("all");
  const [extra, setExtra] = useState("");
  const [items, setItems] = useState<VisualProposal[] | null>(null);
  const [provider, setProvider] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<"plan" | "add" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [previews, setPreviews] = useState<Record<string, RasterImage | string>>({});

  if (!project) return null;
  const chapters = project.template.chapters;
  const chapterName = (code: string) => chapters.find((c) => c.chapter_number === code)?.chapter_title ?? "";

  const plan = async () => {
    setBusy("plan");
    setError(null);
    setNotes({});
    setPreviews({});
    try {
      const r = await api.planVisuals(project.id, chapter === "all" ? [] : [chapter], extra.trim());
      setItems(r.items);
      setProvider(r.provider);
      setPicked(new Set(r.items.map((i) => i.id)));
    } catch (e) {
      setItems(null);
      setError(e instanceof Error ? e.message : "Gagal membuat saran");
    } finally {
      setBusy(null);
    }
  };

  const preview = async (it: VisualProposal) => {
    setPreviews((p) => ({ ...p, [it.id]: "…" }));
    try {
      const img = await renderDiagramPng("mermaid", it.mermaid);
      setPreviews((p) => ({ ...p, [it.id]: img }));
    } catch (e) {
      setPreviews((p) => ({ ...p, [it.id]: `Gagal merender: ${e instanceof Error ? e.message : "kroki.io tidak terjangkau"}` }));
    }
  };

  const toggle = (id: string) =>
    setPicked((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const addSelected = async () => {
    if (!items) return;
    setBusy("add");
    setError(null);
    const remaining: VisualProposal[] = [];
    for (const it of items) {
      if (!picked.has(it.id)) {
        remaining.push(it);
        continue;
      }
      try {
        if (it.type === "table") {
          await addTable({ title: it.title, caption: it.caption, columns: it.columns, rows: it.rows, note: it.note, chapter: it.chapter });
        } else {
          const cached = previews[it.id];
          const img = cached && typeof cached === "object" ? cached : await renderDiagramPng("mermaid", it.mermaid);
          await addDiagram({
            engine: "mermaid",
            title: it.title,
            code: it.mermaid,
            caption: it.caption,
            image: img.dataUrl,
            width: img.width,
            height: img.height,
            chapter: it.chapter,
          });
        }
      } catch (e) {
        setNotes((n) => ({ ...n, [it.id]: e instanceof Error ? e.message : "Gagal ditambahkan" }));
        remaining.push(it);
      }
    }
    setItems(remaining);
    setPicked(new Set(remaining.map((i) => i.id)));
    setBusy(null);
  };

  const needData = (items ?? []).filter((i) => i.needs_data && picked.has(i.id)).length;

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="midnight">
          <Sparkles size={12} /> Saran AI per bab
        </Pill>
        <Pill>{METHOD_HINT[project.form.method]}</Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Tabel dan diagram yang cocok untuk penelitian Anda</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        AI membaca judul, jenis penelitian, bahasa, struktur bab, dan isi yang sudah ditulis, lalu mengusulkan tabel dan diagram untuk tiap bab. Data
        penelitian tidak pernah dikarang: sel yang butuh data Anda diisi penanda <span className="rounded-[3px] bg-marigold/40 px-0.5">[DATA: …]</span>.
        Tabel penelitian relevan di Bab II dibuat dari rujukan yang Anda pilih.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-[220px_1fr_auto] sm:items-end">
        <div>
          <Label htmlFor="pchapter">Bab</Label>
          <Select id="pchapter" value={chapter} onChange={(e) => setChapter(e.target.value)} disabled={busy !== null}>
            <option value="all">Semua bab</option>
            {chapters.map((c) => (
              <option key={c.chapter_number} value={c.chapter_number}>
                BAB {c.chapter_number} · {c.chapter_title}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="pextra">Permintaan tambahan (opsional)</Label>
          <Input id="pextra" value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Contoh: tambahkan diagram alur penelitian dan tabel kisi-kisi wawancara" />
        </div>
        <Button onClick={plan} disabled={busy !== null}>
          {busy === "plan" ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
          {busy === "plan" ? "Menyusun saran…" : items ? "Buat saran baru" : "Buat saran AI"}
        </Button>
      </div>

      {error && (
        <p className="mt-3 flex items-start gap-1.5 text-[13px] text-vermillion">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {error}
        </p>
      )}

      {items && items.length === 0 && <p className="mt-4 text-[13px] text-black/50">Semua usulan sudah ditambahkan. Buat saran baru untuk bab lain.</p>}

      {items && items.length > 0 && (
        <div className="mt-5 space-y-3">
          <p className="text-[12px] text-black/45">
            {items.length} usulan{provider ? ` · disusun oleh ${provider}` : ""}. Centang yang ingin dipakai.
          </p>
          {items.map((it) => {
            const pv = previews[it.id];
            return (
              <div key={it.id} className={cn("rounded-card border p-3", picked.has(it.id) ? "border-brand/50 bg-sky-tint/40" : "border-hairline bg-white")}>
                <label className="flex cursor-pointer items-start gap-2.5">
                  <input type="checkbox" className="mt-1" checked={picked.has(it.id)} onChange={() => toggle(it.id)} disabled={busy !== null} />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-1.5">
                      <Pill>BAB {it.chapter}</Pill>
                      <Pill tone={it.type === "table" ? "blue" : "coral"}>{it.type === "table" ? "Tabel" : "Diagram"}</Pill>
                      {it.source === "auto" && <Pill tone="green">dari rujukan Anda</Pill>}
                      {it.needs_data && <Pill tone="yellow">butuh data Anda</Pill>}
                    </span>
                    <span className="mt-1.5 block text-[14px] font-semibold text-black/90">{it.title}</span>
                    {it.rationale && <span className="mt-0.5 block text-[12.5px] text-black/55">{it.rationale}</span>}
                    <span className="mt-0.5 block text-[11.5px] text-black/35">{chapterName(it.chapter)}</span>
                  </span>
                </label>

                {it.type === "table" ? (
                  <div className="scroll-thin mt-2 overflow-x-auto pl-6">
                    <table className="w-full min-w-[420px] text-left text-[12px]">
                      <thead className="text-black/50">
                        <tr>
                          {it.columns.map((c) => (
                            <th key={c} className="px-2 py-1 font-medium">
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {it.rows.slice(0, 4).map((r, ri) => (
                          <tr key={ri} className="border-t border-hairline">
                            {r.map((c, ci) => (
                              <td key={ci} className="px-2 py-1 align-top">
                                <Cell text={c} />
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {it.rows.length > 4 && <p className="px-2 pt-1 text-[11px] text-black/40">+ {it.rows.length - 4} baris lainnya</p>}
                  </div>
                ) : (
                  <div className="mt-2 pl-6">
                    <pre className="scroll-thin max-h-32 overflow-auto rounded-btn bg-white p-2 text-[11.5px] leading-snug text-black/70">{it.mermaid}</pre>
                    <Button variant="text" size="sm" className="mt-1" onClick={() => preview(it)} disabled={busy !== null}>
                      <ImageIcon size={13} /> Pratinjau gambar
                    </Button>
                    {typeof pv === "string" && pv !== "…" && <p className="text-[12px] text-vermillion">{pv}</p>}
                    {pv === "…" && <p className="text-[12px] text-black/45">Merender…</p>}
                    {pv && typeof pv === "object" && (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img src={pv.dataUrl} alt={it.title} className="mt-1 max-h-72 rounded-btn border border-hairline bg-white p-2" />
                    )}
                  </div>
                )}
                {notes[it.id] && <p className="mt-2 pl-6 text-[12px] text-vermillion">{notes[it.id]}</p>}
              </div>
            );
          })}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={addSelected} disabled={busy !== null || picked.size === 0}>
              {busy === "add" ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
              {busy === "add" ? "Menambahkan…" : `Tambahkan ${picked.size} terpilih ke naskah`}
            </Button>
            {needData > 0 && (
              <span className="text-[12.5px] text-black/55">{needData} di antaranya berisi penanda [DATA] yang wajib Anda ganti dengan data penelitian sebenarnya.</span>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

const METHOD_HINT: Record<string, string> = {
  KUANTITATIF: "Kuantitatif: statistik, instrumen, uji hipotesis",
  KUALITATIF: "Kualitatif: profil partisipan, tema, alur analisis",
  MIXED_METHODS: "Mixed methods: desain bertahap dan joint display",
  RND: "R&D: model pengembangan, validasi ahli, uji coba",
};
