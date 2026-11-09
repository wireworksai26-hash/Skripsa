"use client";

import { Button } from "@/components/ui/button";
import { Label, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import type { ParsedDraft } from "@/lib/types";
import { AlertTriangle, FileUp, Loader2, X } from "lucide-react";
import { useRef, useState } from "react";

/** Hitung ulang total kata setelah pengguna mengeluarkan bagian dari hasil baca. */
function withoutSection(d: ParsedDraft, code: string): ParsedDraft | null {
  const chapters = d.chapters
    .map((c) => ({ ...c, sections: c.sections.filter((s) => s.section_code !== code) }))
    .filter((c) => c.sections.length > 0);
  if (chapters.length === 0) return null;
  return { ...d, chapters, total_words: chapters.reduce((a, c) => a + c.sections.reduce((b, s) => b + s.words, 0), 0) };
}

export function DraftImport({ value, onChange }: { value: ParsedDraft | null; onChange: (d: ParsedDraft | null) => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [pasted, setPasted] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (job: () => Promise<ParsedDraft>) => {
    setBusy(true);
    setError(null);
    try {
      onChange(await job());
    } catch (e) {
      onChange(null);
      setError(e instanceof Error ? e.message : "Naskah tidak dapat dibaca");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 rounded-card border border-hairline bg-canvas p-4">
      <div>
        <p className="text-[13px] font-semibold text-black/85">Bab yang sudah Anda tulis (opsional)</p>
        <p className="mt-0.5 text-[12.5px] leading-relaxed text-black/55">
          Unggah naskah (.docx, .pdf, atau .txt) atau tempel isinya. Bab dan subbab dikenali dari judul seperti “BAB I” dan “1.1 Latar Belakang”.
          Tulisan Anda tidak akan ditimpa AI tanpa konfirmasi, dan menjadi konteks agar bagian lain yang dibuat selaras.
        </p>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".docx,.pdf,.txt,.md"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void run(() => api.parseDraftFile(f));
          e.target.value = "";
        }}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => fileRef.current?.click()} disabled={busy}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <FileUp size={14} />} Unggah naskah
        </Button>
        <span className="text-[12px] text-black/40">atau tempel di bawah</span>
      </div>

      <div>
        <Label htmlFor="pasted">Tempel teks naskah</Label>
        <Textarea
          id="pasted"
          value={pasted}
          onChange={(e) => setPasted(e.target.value)}
          rows={5}
          placeholder={"BAB I PENDAHULUAN\n1.1 Latar Belakang\nIsi latar belakang Anda…\n1.2 Rumusan Masalah\n…"}
        />
        <Button variant="text" size="sm" className="mt-1" disabled={busy || pasted.trim().length < 100} onClick={() => run(() => api.parseDraftText(pasted))}>
          Baca struktur dari teks
        </Button>
      </div>

      {error && (
        <p className="flex items-start gap-1.5 text-[12.5px] text-vermillion">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {error}
        </p>
      )}

      {value && (
        <div className="space-y-3 border-t border-hairline pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="green">
              {value.chapters.length} bab · {value.chapters.reduce((a, c) => a + c.sections.length, 0)} subbab · {value.total_words.toLocaleString("id-ID")} kata
            </Pill>
            {value.filename && <span className="text-[12px] text-black/45">{value.filename}</span>}
            <Button variant="text" size="sm" onClick={() => onChange(null)}>
              Kosongkan
            </Button>
          </div>
          <ol className="space-y-3">
            {value.chapters.map((c) => (
              <li key={c.chapter_code}>
                <p className="text-[12.5px] font-semibold">
                  BAB {c.chapter_code}
                  {c.chapter_title ? ` · ${c.chapter_title}` : ""}
                </p>
                <ul className="mt-1 space-y-1">
                  {c.sections.map((s) => (
                    <li key={s.section_code} className="flex items-start justify-between gap-2 rounded-btn bg-white px-2.5 py-1.5 text-[12.5px]">
                      <span className="min-w-0">
                        <span className="font-medium">
                          {s.section_code} {s.title}
                        </span>
                        <span className="ml-2 text-black/40">{s.words.toLocaleString("id-ID")} kata</span>
                        <span className="mt-0.5 block truncate text-black/45">{s.content.replace(/\s+/g, " ").slice(0, 110)}…</span>
                      </span>
                      <button
                        type="button"
                        className="shrink-0 rounded-btn p-1 text-black/40 hover:bg-black/5 hover:text-black/70"
                        aria-label={`Keluarkan subbab ${s.section_code}`}
                        title="Jangan impor subbab ini"
                        onClick={() => onChange(withoutSection(value, s.section_code))}
                      >
                        <X size={14} />
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
          {value.warnings.length > 0 && (
            <ul className="space-y-1 rounded-btn border border-saffron/40 bg-saffron/5 p-2.5 text-[12px] text-[#6b4a00]">
              {value.warnings.map((w) => (
                <li key={w}>• {w}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
