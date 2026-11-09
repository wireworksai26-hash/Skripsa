"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { askConfirm } from "@/components/ui/confirm";
import { Input } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api, ApiError } from "@/lib/api";
import { useProject } from "@/lib/store";
import { countWords } from "@/lib/utils";
import { ArrowDown, ArrowUp, CornerDownRight, ListTree, Plus, Save, Trash2, X } from "lucide-react";
import { useState } from "react";

interface Row {
  key: string;
  code: string | null;
  title: string;
  words: number;
  level: 1 | 2;
  hasText: boolean;
}
interface Chap {
  key: string;
  title: string;
  rows: Row[];
}

let seq = 0;
const nextKey = () => `k${++seq}`;

/** Editor struktur bab per proyek: tambah, hapus, ganti nama, urutkan, dan jadikan anak (2.1.1). */
export function StructureEditor({ onClose }: { onClose: () => void }) {
  const project = useProject((s) => s.project);
  const reload = useProject((s) => s.reload);
  const [chapters, setChapters] = useState<Chap[]>(() =>
    project
      ? project.template.chapters.map((c) => ({
          key: nextKey(),
          title: c.chapter_title,
          rows: project.sections
            .filter((s) => s.chapterCode === c.chapter_number)
            .map((s) => ({
              key: nextKey(),
              code: s.sectionCode,
              title: s.title,
              words: s.targetWords,
              level: (s.sectionCode.split(".").length > 2 ? 2 : 1) as 1 | 2,
              hasText: countWords(s.content) > 0,
            })),
        }))
      : []
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!project) return null;

  const setChap = (ci: number, fn: (c: Chap) => Chap) => setChapters((cs) => cs.map((c, i) => (i === ci ? fn(c) : c)));
  const setRow = (ci: number, ri: number, patch: Partial<Row>) => setChap(ci, (c) => ({ ...c, rows: c.rows.map((r, i) => (i === ri ? { ...r, ...patch } : r)) }));
  const move = <T,>(list: T[], i: number, d: -1 | 1): T[] => {
    const j = i + d;
    if (j < 0 || j >= list.length) return list;
    const out = [...list];
    [out[i], out[j]] = [out[j], out[i]];
    return out;
  };

  // Subbab tingkat 2 tidak boleh berada di awal bab (belum ada induk).
  const invalid = chapters.findIndex((c) => c.rows[0]?.level === 2);
  const empty = chapters.some((c) => !c.title.trim() || c.rows.some((r) => !r.title.trim()));
  const kept = new Set(chapters.flatMap((c) => c.rows.map((r) => r.code).filter(Boolean)));
  const removedWithText = project.sections.filter((s) => !kept.has(s.sectionCode) && countWords(s.content) > 0);

  const save = async () => {
    if (removedWithText.length > 0) {
      const ok = await askConfirm(`Subbab berikut berisi tulisan dan akan dihapus permanen: ${removedWithText.map((s) => `${s.sectionCode} ${s.title}`).join("; ")}.`, {
        title: "Hapus subbab berisi tulisan?",
        confirmLabel: "Hapus dan simpan",
        danger: true,
      });
      if (!ok) return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.saveStructure(
        project.id,
        chapters.map((c) => ({ title: c.title.trim(), sections: c.rows.map((r) => ({ code: r.code, title: r.title.trim(), target_words: r.words, level: r.level })) })),
        removedWithText.length > 0
      );
      await reload();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Gagal menyimpan struktur");
    } finally {
      setBusy(false);
    }
  };

  const iconBtn = "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-btn text-black/60 hover:bg-black/5 disabled:opacity-30";

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">
          <ListTree size={12} /> Struktur bab
        </Pill>
        <Pill>{chapters.reduce((a, c) => a + c.rows.length, 0)} subbab</Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Atur struktur sesuai pembimbing Anda</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Tambah, hapus, ganti nama, dan urutkan subbab. Tombol <CornerDownRight size={12} className="inline" /> menjadikan subbab sebagai anak (mis. 2.1.1). Tulisan pada subbab yang dipertahankan ikut pindah ke nomor barunya.
      </p>

      <div className="mt-4 space-y-5">
        {chapters.map((c, ci) => (
          <div key={c.key} className="rounded-card border border-hairline p-3">
            <div className="flex items-center gap-1.5">
              <span className="w-12 shrink-0 text-[12px] font-semibold text-black/50">BAB {ci + 1}</span>
              <Input aria-label={`Judul bab ${ci + 1}`} value={c.title} onChange={(e) => setChap(ci, (x) => ({ ...x, title: e.target.value }))} />
              <button className={iconBtn} aria-label="Pindah bab ke atas" disabled={ci === 0} onClick={() => setChapters((cs) => move(cs, ci, -1))}>
                <ArrowUp size={15} />
              </button>
              <button className={iconBtn} aria-label="Pindah bab ke bawah" disabled={ci === chapters.length - 1} onClick={() => setChapters((cs) => move(cs, ci, 1))}>
                <ArrowDown size={15} />
              </button>
              <button
                className={`${iconBtn} text-vermillion`}
                aria-label="Hapus bab"
                disabled={chapters.length === 1}
                onClick={async () => {
                  if (c.rows.some((r) => r.hasText) && !(await askConfirm(`Bab ${ci + 1} berisi subbab bertulisan. Hapus seluruh bab?`, { danger: true, confirmLabel: "Hapus bab" }))) return;
                  setChapters((cs) => cs.filter((_, i) => i !== ci));
                }}
              >
                <Trash2 size={15} />
              </button>
            </div>

            <ul className="mt-2 space-y-1.5">
              {c.rows.map((r, ri) => (
                <li key={r.key} className={`flex items-center gap-1.5 ${r.level === 2 ? "pl-6 sm:pl-10" : ""}`}>
                  <button
                    className={`${iconBtn} ${r.level === 2 ? "bg-sky-tint text-brand" : ""}`}
                    aria-label={r.level === 2 ? "Jadikan subbab tingkat 1" : "Jadikan anak dari subbab di atasnya"}
                    aria-pressed={r.level === 2}
                    disabled={ri === 0}
                    onClick={() => setRow(ci, ri, { level: r.level === 2 ? 1 : 2 })}
                  >
                    <CornerDownRight size={15} />
                  </button>
                  <Input aria-label="Judul subbab" value={r.title} onChange={(e) => setRow(ci, ri, { title: e.target.value })} />
                  <input
                    aria-label="Target kata"
                    type="number"
                    inputMode="numeric"
                    min={50}
                    max={4000}
                    step={50}
                    value={r.words}
                    onChange={(e) => setRow(ci, ri, { words: Math.max(50, Math.min(4000, Number(e.target.value) || 50)) })}
                    className="hidden h-11 w-20 shrink-0 rounded-btn border border-hairline bg-white px-2 text-base sm:block lg:text-[14px]"
                  />
                  <button className={iconBtn} aria-label="Naikkan" disabled={ri === 0} onClick={() => setChap(ci, (x) => ({ ...x, rows: move(x.rows, ri, -1) }))}>
                    <ArrowUp size={15} />
                  </button>
                  <button className={iconBtn} aria-label="Turunkan" disabled={ri === c.rows.length - 1} onClick={() => setChap(ci, (x) => ({ ...x, rows: move(x.rows, ri, 1) }))}>
                    <ArrowDown size={15} />
                  </button>
                  <button className={`${iconBtn} text-vermillion`} aria-label="Hapus subbab" onClick={() => setChap(ci, (x) => ({ ...x, rows: x.rows.filter((_, i) => i !== ri) }))}>
                    <X size={15} />
                  </button>
                </li>
              ))}
            </ul>
            <Button
              className="mt-2"
              variant="text"
              size="sm"
              onClick={() => setChap(ci, (x) => ({ ...x, rows: [...x.rows, { key: nextKey(), code: null, title: "", words: 400, level: 1, hasText: false }] }))}
            >
              <Plus size={14} /> Tambah subbab
            </Button>
          </div>
        ))}
        <Button variant="ghost" disabled={chapters.length >= 12} onClick={() => setChapters((cs) => [...cs, { key: nextKey(), title: "", rows: [{ key: nextKey(), code: null, title: "", words: 400, level: 1, hasText: false }] }])}>
          <Plus size={15} /> Tambah bab
        </Button>
      </div>

      {invalid >= 0 && <p className="mt-3 text-[13px] text-vermillion">Bab {invalid + 1}: subbab pertama tidak boleh berupa anak.</p>}
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}
      <div className="mt-5 flex flex-wrap gap-2">
        <Button onClick={save} loading={busy} disabled={busy || invalid >= 0 || empty}>
          {!busy && <Save size={15} />} Simpan struktur
        </Button>
        <Button variant="text" onClick={onClose} disabled={busy}>
          Batal
        </Button>
      </div>
    </Card>
  );
}
