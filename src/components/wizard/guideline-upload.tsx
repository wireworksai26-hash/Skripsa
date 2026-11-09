"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { totalTargetWords, type CampusTemplate, type GuidelineReport } from "@/lib/templates";
import { cn } from "@/lib/utils";
import { AlertTriangle, BadgeCheck, FileUp, Loader2 } from "lucide-react";
import { useRef, useState } from "react";

interface Parsed {
  template: CampusTemplate;
  report: GuidelineReport;
  filename: string;
}

/** Baris ringkasan: nilai + label apakah terbaca dari PDF atau memakai nilai bawaan. */
function Row({ label, value, fromPdf }: { label: string; value: string; fromPdf: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-dashed border-hairline py-1.5 text-[12.5px]">
      <dt className="text-black/50">{label}</dt>
      <dd className="flex items-center gap-2 text-right font-medium">
        {value}
        <span
          className={cn(
            "rounded-pill px-2 py-0.5 text-[10.5px] font-medium",
            fromPdf ? "bg-[#e8f6e8] text-[#0a4d1e]" : "bg-saffron/15 text-[#6b4a00]"
          )}
        >
          {fromPdf ? "dari PDF" : "bawaan"}
        </span>
      </dd>
    </div>
  );
}

const EVIDENCE_LABEL: Record<string, string> = {
  margins: "Margin",
  font: "Huruf",
  spacing: "Spasi",
  citation: "Sitasi",
  chapters: "Sistematika bab",
};

export function GuidelineUpload({
  degree,
  method,
  onSaved,
}: {
  degree: string;
  method: string;
  onSaved: (templateId: string) => Promise<void> | void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"parse" | "save" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [name, setName] = useState("");

  const pick = async (file: File) => {
    setError(null);
    setParsed(null);
    setBusy("parse");
    try {
      const out = await api.parseGuideline(file, degree, method);
      setParsed({ ...out, filename: file.name });
      setName(out.template.campus_name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "PDF tidak dapat diproses");
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    if (!parsed) return;
    setBusy("save");
    setError(null);
    try {
      const saved = await api.saveCustomTemplate({ template: parsed.template, name: name.trim(), filename: parsed.filename, report: parsed.report });
      setParsed(null);
      await onSaved(saved.campus_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Templat tidak tersimpan");
    } finally {
      setBusy(null);
    }
  };

  const t = parsed?.template;
  const rep = parsed?.report;
  const got = (label: string) => !!rep?.extracted.includes(label);

  return (
    <Card>
      <div className="flex items-start gap-3">
        <FileUp size={18} className="mt-0.5 shrink-0 text-black/70" />
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-black/90">Pedoman kampus sendiri (PDF)</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-black/65">
            Unggah buku pedoman skripsi kampus Anda. Margin, huruf, spasi, gaya sitasi, dan sistematika bab dibaca otomatis menjadi templat.
            PDF harus berisi teks (bukan hasil pindai).
          </p>

          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void pick(f);
              e.target.value = "";
            }}
          />
          {!parsed && (
            <Button variant="ghost" size="sm" className="mt-3" onClick={() => fileRef.current?.click()} disabled={busy !== null}>
              {busy === "parse" ? <Loader2 size={14} className="animate-spin" /> : <FileUp size={14} />}
              {busy === "parse" ? "Membaca PDF…" : "Pilih PDF pedoman"}
            </Button>
          )}
          {busy === "parse" && <p className="mt-2 text-[12px] text-black/50">Mengekstrak teks dan aturan; bisa 10–30 detik untuk pedoman tebal.</p>}
          {error && (
            <p className="mt-3 flex items-start gap-1.5 text-[12.5px] text-vermillion">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {error}
            </p>
          )}

          {t && rep && (
            <div className="mt-4 space-y-4">
              <div>
                <Label htmlFor="tplname">Nama templat</Label>
                <Input id="tplname" value={name} onChange={(e) => setName(e.target.value)} />
                <p className="mt-1 text-[11.5px] text-black/45">
                  {rep.filename} · {rep.pages} halaman, {rep.pages_used} dibaca · diekstrak oleh {rep.provider}
                </p>
              </div>

              <dl>
                <Row label="Kertas" value={t.page_setup.paper_size} fromPdf={got("ukuran kertas")} />
                <Row
                  label="Margin (atas-kiri-bawah-kanan)"
                  value={`${t.page_setup.margins_cm.top}-${t.page_setup.margins_cm.left}-${t.page_setup.margins_cm.bottom}-${t.page_setup.margins_cm.right} cm`}
                  fromPdf={["top", "left", "bottom", "right"].every((s) => got(`margin ${s}`))}
                />
                <Row label="Jenis huruf" value={t.page_setup.font_family} fromPdf={got("jenis huruf")} />
                <Row label="Ukuran huruf" value={`${t.page_setup.font_size_pt} pt`} fromPdf={got("ukuran huruf")} />
                <Row label="Spasi baris" value={String(t.page_setup.line_spacing)} fromPdf={got("spasi baris")} />
                <Row label="Indentasi paragraf" value={`${t.page_setup.paragraph_indent_cm} cm`} fromPdf={got("indentasi paragraf")} />
                <Row label="Gaya sitasi" value={t.citation_style.replace("_", " ")} fromPdf={got("gaya sitasi")} />
                <Row
                  label="Sistematika"
                  value={`${t.chapters.length} bab · ${t.chapters.reduce((a, c) => a + c.sub_sections.length, 0)} subbab · ${totalTargetWords(t).toLocaleString("id-ID")} kata`}
                  fromPdf={got("sistematika bab")}
                />
              </dl>

              <details className="rounded-btn border border-hairline bg-white p-2 text-[12.5px]">
                <summary className="cursor-pointer font-medium text-black/70">Lihat bab dan subbab</summary>
                <ol className="mt-2 space-y-2">
                  {t.chapters.map((c) => (
                    <li key={c.chapter_number}>
                      <p className="font-semibold">
                        BAB {c.chapter_number} · {c.chapter_title}
                      </p>
                      <ul className="ml-3 list-disc text-black/65">
                        {c.sub_sections.map((s) => (
                          <li key={s.code}>
                            {s.code} {s.title} <span className="text-black/35">· {s.target_words} kata</span>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ol>
              </details>

              {Object.keys(rep.evidence).length > 0 && (
                <div>
                  <p className="text-[12px] font-semibold text-black/60">Kutipan bukti dari PDF</p>
                  <ul className="mt-1 space-y-1.5">
                    {Object.entries(rep.evidence).map(([k, ev]) => (
                      <li key={k} className="flex gap-2 text-[12px] leading-relaxed">
                        {ev.verified ? (
                          <BadgeCheck size={14} className="mt-0.5 shrink-0 text-brand" aria-label="ditemukan di PDF" />
                        ) : (
                          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-saffron" aria-label="tidak ditemukan di PDF" />
                        )}
                        <span>
                          <strong>{EVIDENCE_LABEL[k] ?? k}:</strong> <span className="text-black/65">“{ev.quote}”</span>
                          {!ev.verified && <span className="ml-1 text-[#6b4a00]">(tidak ditemukan persis di PDF)</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {rep.warnings.length > 0 && (
                <ul className="space-y-1 rounded-btn border border-saffron/40 bg-saffron/5 p-2.5 text-[12px] text-[#6b4a00]">
                  {rep.warnings.map((w) => (
                    <li key={w}>• {w}</li>
                  ))}
                </ul>
              )}
              {rep.defaulted.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-black/55">
                  <Pill tone="yellow">memakai nilai bawaan</Pill> {rep.defaulted.join(", ")} — tidak tertulis jelas di pedoman.
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button variant="primary" size="sm" onClick={save} disabled={busy !== null || name.trim().length < 2}>
                  {busy === "save" && <Loader2 size={14} className="animate-spin" />} Simpan &amp; pakai templat ini
                </Button>
                <Button variant="text" size="sm" onClick={() => setParsed(null)} disabled={busy !== null}>
                  Batal
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
