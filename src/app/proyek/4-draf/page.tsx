"use client";

import { askConfirm } from "@/components/ui/confirm";
import { StructureEditor } from "@/components/wizard/structure-editor";
import { VersionHistory } from "@/components/wizard/version-history";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { PdfViewer } from "@/components/pdf/pdf-viewer";
import { useProject } from "@/lib/store";
import { countWords, cn } from "@/lib/utils";
import {
  AlertTriangle,
  FileSearch,
  FileText,
  ListTree,
  Highlighter,
  Loader2,
  MoveRight,
  Pencil,
  RefreshCw,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { InlineCitation, Section } from "@/lib/types";

interface OpenPdf {
  citationId: string;
  snippet: string;
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
const roman = (code: string) => ROMAN[Number(code) - 1] ?? code;
const emptyDraft = (s: Section) => countWords(s.content) < 10; // daftar rumusan masalah/tujuan yang sah bisa < 30 kata

interface ChapterGroup {
  code: string;
  title: string;
  sections: Section[];
  words: number;
  target: number;
  filled: number;
}

export default function DrafPage() {
  const router = useRouter();
  const project = useProject((s) => s.project);
  const ensureSections = useProject((s) => s.ensureSections);
  const generateSection = useProject((s) => s.generateSection);
  const editSection = useProject((s) => s.editSection);
  const persistSection = useProject((s) => s.persistSection);

  const [chapterCode, setChapterCode] = useState<string | null>(null);
  const [editingStructure, setEditingStructure] = useState(false);
  const [autoSuggest, setAutoSuggest] = useState(false);
  const [activeCode, setActiveCode] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number; code: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [viewer, setViewer] = useState<OpenPdf | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!project) {
      router.replace("/proyek/1-inisiasi");
      return;
    }
    ensureSections().catch((e) => setError(e instanceof Error ? e.message : "Gagal menyiapkan subbab"));
  }, [project?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
  }, []);

  if (!project) return null;

  // Pengaman: kode subbab ganda (data lama) tidak boleh merusak daftar.
  const unique = [...new Map(project.sections.map((s) => [s.sectionCode, s])).values()];
  const byCode = new Map<string, Section[]>();
  for (const s of unique) byCode.set(s.chapterCode, [...(byCode.get(s.chapterCode) ?? []), s]);
  const groups: ChapterGroup[] = [...byCode.entries()]
    .sort(([x], [y]) => Number(x) - Number(y))
    .map(([code, secs]) => ({
      code,
      title: project.template.chapters.find((c) => c.chapter_number === code)?.chapter_title ?? "",
      sections: secs,
      words: secs.reduce((a, x) => a + countWords(x.content), 0),
      target: secs.reduce((a, x) => a + x.targetWords, 0),
      filled: secs.filter((x) => !emptyDraft(x)).length,
    }));

  const pickedTitle = project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? project.form.topic;
  const selectedRefs = project.references.filter((r) => project.selectedRefIds.includes(r.id));
  const current = groups.find((g) => g.code === chapterCode) ?? groups.find((g) => g.sections.some(emptyDraft)) ?? groups[0];
  const currentIdx = current ? groups.indexOf(current) : -1;
  const nextGroup = currentIdx >= 0 ? groups[currentIdx + 1] : undefined;
  const active = current?.sections.find((s) => s.sectionCode === activeCode) ?? current?.sections[0];

  const totalWords = groups.reduce((a, g) => a + g.words, 0);
  const totalTarget = groups.reduce((a, g) => a + g.target, 0);
  const providers = [...new Set(unique.map((s) => s.provider).filter(Boolean))];
  const importedCount = unique.filter((s) => s.origin === "IMPORTED" && countWords(s.content) > 0).length;
  const busy = !!progress;
  const canGenerate = selectedRefs.length > 0 && !busy;

  const pickChapter = (code: string) => {
    setChapterCode(code);
    setActiveCode(null);
    setEditing(false);
    setViewer(null);
  };

  const generateMany = async (list: Section[], overwrite: Set<string> = new Set()) => {
    setError(null);
    setProgress({ done: 0, total: list.length, code: list[0]?.sectionCode ?? "" });
    for (let i = 0; i < list.length; i++) {
      setActiveCode(list[i].sectionCode);
      setProgress({ done: i, total: list.length, code: list[i].sectionCode });
      try {
        await generateSection(list[i].sectionCode, overwrite.has(list[i].sectionCode));
      } catch (e) {
        setError(`Subbab ${list[i].sectionCode} gagal: ${e instanceof Error ? e.message : e}`);
        break;
      }
    }
    setProgress(null);
  };

  // Pembuatan massal tidak pernah menyentuh tulisan pengguna; menimpa satu subbab butuh konfirmasi tersendiri.
  const missing = current ? current.sections.filter((s) => s.origin !== "IMPORTED" && emptyDraft(s)) : [];
  const regenerable = current ? current.sections.filter((s) => s.origin !== "IMPORTED") : [];

  const generateChapter = () => generateMany(missing);

  const regenerateChapter = async () => {
    if (!current) return;
    const overwritten = regenerable.filter((s) => !emptyDraft(s)).length;
    if (overwritten > 0 && !(await askConfirm(`Buat ulang Bab ${current.code}? ${overwritten} subbab yang sudah berisi akan diganti draf baru.`, { danger: false }))) return;
    return generateMany(regenerable);
  };

  const regenerateOne = async (sec: Section) => {
    if (sec.origin === "IMPORTED" && countWords(sec.content) > 0) {
      if (!(await askConfirm(`Subbab ${sec.sectionCode} berisi tulisan Anda. Ganti dengan draf baru buatan agen? Tulisan lama akan hilang.`, { danger: false }))) return;
      return generateMany([sec], new Set([sec.sectionCode]));
    }
    if (!emptyDraft(sec) && !(await askConfirm(`Buat ulang subbab ${sec.sectionCode}? Isi saat ini akan diganti.`, { danger: false }))) return;
    return generateMany([sec]);
  };

  const onEdit = (code: string, content: string) => {
    editSection(code, content);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      persistSection(code).catch((e) => setError(e instanceof Error ? e.message : "Gagal menyimpan suntingan"));
    }, 800);
  };

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="coral">
            <Wand2 size={12} /> Academic Writer Agent
          </Pill>
          {providers.length > 0 && <Pill tone="midnight">Ditulis oleh {providers.join(", ")}</Pill>}
          {importedCount > 0 && <Pill tone="coral">{importedCount} subbab tulisan Anda (aman dari penimpaan massal)</Pill>}
          <Pill tone={selectedRefs.length ? "blue" : "coral"}>{selectedRefs.length} rujukan aktif</Pill>
        </div>
        <h1 className="t-heading mt-4">Draf per bab &amp; verifikasi kutipan</h1>
        <p className="t-serif-lede mt-2 text-graphite">
          Kerjakan satu bab dalam satu waktu: pilih bab di bawah, buat semua subbabnya, periksa dan sunting, lalu lanjut ke bab berikutnya.
          Klik penanda sitasi di naskah untuk membuka PDF dengan kalimat rujukan yang disorot kuning.
        </p>

        {selectedRefs.length === 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-btn border border-vermillion/30 bg-vermillion/5 p-3 text-[13px] text-vermillion">
            <AlertTriangle size={15} className="shrink-0" />
            <span>Tombol buat aktif setelah Anda memilih minimal 1 rujukan (disarankan 8 atau lebih) di Langkah 3. Draf hanya boleh bersandar pada rujukan nyata.</span>
            <Button size="sm" variant="primary" onClick={() => router.push("/proyek/3-rujukan")}>
              Pilih rujukan
            </Button>
          </div>
        )}

        <div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <div>
            <Label htmlFor="chapter">Bab yang dikerjakan</Label>
            <Select id="chapter" value={current?.code ?? ""} onChange={(e) => pickChapter(e.target.value)} disabled={busy}>
              {groups.map((g) => (
                <option key={g.code} value={g.code}>
                  {`BAB ${roman(g.code)}${g.title ? ` · ${g.title}` : ""} — ${g.filled}/${g.sections.length} subbab terisi, ${g.words.toLocaleString("id-ID")} kata`}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {current && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={generateChapter} disabled={!canGenerate || missing.length === 0}>
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />}
              {missing.length > 0 ? `Buat Bab ${roman(current.code)} (${missing.length} subbab kosong)` : `Bab ${roman(current.code)} sudah terisi`}
            </Button>
            <Button variant="ghost" onClick={regenerateChapter} disabled={!canGenerate || regenerable.length === 0}>
              <RefreshCw size={14} /> Buat ulang Bab {roman(current.code)}
            </Button>
            {nextGroup ? (
              <Button variant="text" onClick={() => pickChapter(nextGroup.code)} disabled={busy}>
                Bab berikutnya: BAB {roman(nextGroup.code)} <MoveRight size={14} />
              </Button>
            ) : (
              <Button variant="text" onClick={() => router.push("/proyek/5-visual")} disabled={busy}>
                Lanjut: Visual <MoveRight size={14} />
              </Button>
            )}
            <Button variant="text" onClick={() => { setAutoSuggest(false); setEditingStructure(true); }} disabled={busy}>
              <ListTree size={14} /> Ubah struktur bab
            </Button>
            <Button variant="text" onClick={() => { setAutoSuggest(true); setEditingStructure(true); }} disabled={busy}>
              <Sparkles size={14} /> Sub-subbab (AI)
            </Button>
            {progress && (
              <Pill tone="yellow">
                <Loader2 size={11} className="animate-spin" /> Membuat subbab {progress.code} ({progress.done + 1}/{progress.total})…
              </Pill>
            )}
          </div>
        )}

        {error && (
          <p className="mt-3 flex items-center gap-1.5 text-[13px] text-vermillion">
            <AlertTriangle size={13} /> {error}
          </p>
        )}

        <div className="mt-4">
          <div className="flex items-center justify-between text-[12px] text-black/55">
            <span>Progres seluruh naskah</span>
            <span>
              {totalWords.toLocaleString("id-ID")} / {totalTarget.toLocaleString("id-ID")} kata
            </span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-pill bg-black/8">
            <div className="h-full rounded-pill bg-brand transition-all" style={{ width: `${Math.min(100, (totalWords / Math.max(totalTarget, 1)) * 100)}%` }} />
          </div>
        </div>
      </Card>

      {editingStructure && <StructureEditor key={String(autoSuggest)} autoSuggest={autoSuggest} onClose={() => setEditingStructure(false)} />}

      <div className={cn("grid gap-4", viewer ? "lg:grid-cols-2" : "lg:grid-cols-[1fr_380px]")}>
        <div className={cn("space-y-3", viewer && "hidden")}>
          {current?.sections.map((s) => {
            const words = countWords(s.content);
            const isActive = active?.sectionCode === s.sectionCode;
            const generating = progress?.code === s.sectionCode;
            return (
              <div
                key={s.sectionCode}
                role="button"
                tabIndex={0}
                onClick={() => {
                  setActiveCode(s.sectionCode);
                  setEditing(false);
                  scrollToPanel();
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setActiveCode(s.sectionCode);
                    setEditing(false);
                    scrollToPanel();
                  }
                }}
                className={cn(
                  "w-full cursor-pointer rounded-card border bg-white p-4 text-left transition-colors duration-200",
                  isActive ? "border-brand" : "border-hairline hover:bg-black/[0.03]"
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-black/95">
                    {s.sectionCode} {s.title}
                    {s.origin === "IMPORTED" && words > 0 && (
                      <span className="ml-2 rounded-pill bg-marigold/40 px-2 py-0.5 align-middle text-[10.5px] font-medium text-black/70">tulisan Anda</span>
                    )}
                  </p>
                  <Pill tone={words >= s.targetWords * 0.8 && words > 0 ? "green" : words > 0 ? "yellow" : "basic"}>
                    {words}/{s.targetWords} kata
                  </Pill>
                </div>
                {words === 0 ? (
                  <p className="mt-1 flex items-center gap-1.5 text-[12px] text-black/40">
                    <FileText size={12} /> Belum ada draf
                  </p>
                ) : (
                  <p className="mt-1 line-clamp-2 text-[13px] text-black/55">{s.content.replace(/\n/g, " ").slice(0, 150)}…</p>
                )}
                <div className="mt-3">
                  <Button
                    size="sm"
                    variant={words === 0 ? "primary" : "ghost"}
                    disabled={!canGenerate}
                    onClick={(e) => {
                      e.stopPropagation();
                      void regenerateOne(s);
                    }}
                  >
                    {generating ? <Loader2 size={13} className="animate-spin" /> : words === 0 ? <Wand2 size={13} /> : <RefreshCw size={13} />}
                    {generating ? "Membuat…" : words === 0 ? "Buat subbab ini" : "Buat ulang"}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        {active && (
          <DocPanel
            section={active}
            title={pickedTitle}
            editing={editing}
            canGenerate={canGenerate}
            onEditToggle={() => setEditing((v) => !v)}
            onRegenerate={() => regenerateOne(active)}
            onChange={(content) => onEdit(active.sectionCode, content)}
            onOpenPdf={(citationId, snippet) => setViewer({ citationId, snippet })}
            openCitationId={viewer?.citationId}
          />
        )}

        {viewer && (
          <div className="safe-top safe-bottom fixed inset-0 z-50 bg-canvas p-2 lg:static lg:z-auto lg:h-[calc(100dvh-7.5rem)] lg:bg-transparent lg:p-0 lg:sticky lg:top-24">
            <PdfViewer
              key={`${viewer.citationId}:${viewer.snippet}`}
              thesisId={project.id}
              citationId={viewer.citationId}
              title={project.references.find((r) => r.id === viewer.citationId)?.title ?? "Rujukan"}
              snippet={viewer.snippet}
              externalUrl={project.references.find((r) => r.id === viewer.citationId)?.oaUrl}
              hasPdf={!!project.references.find((r) => r.id === viewer.citationId)?.oaUrl}
              onClose={() => setViewer(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

/** Di layar sempit daftar subbab dan draf bertumpuk; setelah memilih subbab, bawa pengguna ke drafnya. */
function scrollToPanel() {
  if (typeof window === "undefined" || window.matchMedia("(min-width: 1024px)").matches) return;
  requestAnimationFrame(() => document.getElementById("doc-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

function DocPanel({
  section,
  title,
  editing,
  canGenerate,
  onEditToggle,
  onRegenerate,
  onChange,
  onOpenPdf,
  openCitationId,
}: {
  section: Section;
  title: string;
  editing: boolean;
  canGenerate: boolean;
  onEditToggle: () => void;
  onRegenerate: () => void;
  onChange: (content: string) => void;
  onOpenPdf: (citationId: string, snippet: string) => void;
  openCitationId?: string;
}) {
  const project = useProject((s) => s.project);
  if (!project) return null;

  return (
    <div id="doc-panel" className="scroll-mt-20 lg:sticky lg:top-24 lg:self-start">
      <Card className="flex h-full flex-col">
        <div className="flex items-center justify-between gap-2">
          <p className="font-semibold text-black/95">
            {section.sectionCode} {section.title}
          </p>
          <div className="flex gap-1">
            <Button variant="text" size="sm" onClick={onEditToggle} aria-label="Mode edit">
              <Pencil size={14} />
            </Button>
            <Button variant={section.content.trim() ? "ghost" : "primary"} size="sm" onClick={onRegenerate} disabled={!canGenerate} aria-label="Buat ulang draf">
              <RefreshCw size={14} /> {section.content.trim() ? "Buat ulang" : "Buat subbab ini"}
            </Button>
          </div>
        </div>
        <p className="text-[12px] text-black/45">draf · {title}</p>

        <div className="mt-3 flex-1">
          {editing ? (
            <textarea
              className="scroll-thin h-80 w-full rounded-btn border border-hairline bg-white p-3 text-base leading-relaxed outline-none focus:border-brand sm:text-[14px]"
              value={section.content}
              onChange={(e) => onChange(e.target.value)}
            />
          ) : section.content ? (
            <div className="scroll-thin max-h-[26rem] space-y-3 overflow-y-auto pr-1 text-[14px] leading-relaxed text-charcoal">
              {section.content.split(/\n+/).map((p, i) => (
                <p key={i}>{withCitationLinks(p, section.citations, onOpenPdf, openCitationId)}</p>
              ))}
            </div>
          ) : (
            <div className="grid h-40 place-items-center rounded-btn border border-dashed border-hairline text-[13px] text-black/40">
              Draf akan muncul di sini
            </div>
          )}
        </div>

        <GroundingPanel section={section} onOpenPdf={onOpenPdf} openCitationId={openCitationId} />
        <VersionHistory key={section.sectionCode} thesisId={project.id} code={section.sectionCode} current={section.content} />
      </Card>
    </div>
  );
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Ubah penanda sitasi di paragraf menjadi tombol yang membuka PDF dan menyorot kalimat rujukannya. */
function withCitationLinks(
  text: string,
  citations: InlineCitation[],
  onOpenPdf: (citationId: string, snippet: string) => void,
  openCitationId?: string
) {
  const byMarker = new Map<string, InlineCitation>();
  for (const c of citations) if (c.marker && !byMarker.has(c.marker)) byMarker.set(c.marker, c);
  if (byMarker.size === 0) return text;

  const pattern = new RegExp(
    `(${[...byMarker.keys()].sort((a, b) => b.length - a.length).map(escapeRegExp).join("|")})`
  );
  return text.split(pattern).map((part, i) => {
    const c = byMarker.get(part);
    if (!c) return part;
    return (
      <button
        key={i}
        type="button"
        onClick={() => onOpenPdf(c.referenceId, c.snippet)}
        title="Buka PDF dan sorot kalimat rujukan"
        className={cn(
          "rounded-[3px] px-0.5 font-medium underline decoration-saffron/60 underline-offset-2 hover:bg-marigold/60",
          openCitationId === c.referenceId ? "bg-marigold/60" : "bg-marigold/30"
        )}
      >
        {part}
      </button>
    );
  });
}

function GroundingPanel({
  section,
  onOpenPdf,
  openCitationId,
}: {
  section: Section;
  onOpenPdf: (citationId: string, snippet: string) => void;
  openCitationId?: string;
}) {
  const project = useProject((s) => s.project);
  if (!project) return null;
  const byId = new Map(project.references.map((r) => [r.id, r]));
  const refs = section.citations.map((c) => ({ c, r: byId.get(c.referenceId) }));

  return (
    <div className="mt-5 border-t border-hairline pt-4">
      <div className="flex items-center gap-2">
        <Highlighter size={15} className="text-marigold" />
        <p className="text-[13px] font-semibold">Visual grounding · stabilo kuning</p>
      </div>
      {refs.length === 0 ? (
        <p className="mt-2 text-[12px] text-black/45">
          Belum ada kutipan pada subbab ini.
        </p>
      ) : (
        <ul className="scroll-thin mt-3 max-h-72 space-y-3 overflow-y-auto pr-1">
          {refs.map(({ c, r }, i) => (
            <li key={`${c.referenceId}-${i}`} className="rounded-btn border border-hairline bg-canvas p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="rounded-pill bg-marigold px-2.5 py-0.5 text-[11px] font-semibold text-black">
                  {c.marker}
                </span>
                {r?.doi && (
                  <a
                    href={`https://doi.org/${r.doi}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] font-medium text-brand underline"
                  >
                    DOI aktif
                  </a>
                )}
              </div>
              {r && (
                <p className="mt-2 text-[12px] text-black/70">
                  {r.authors[0]}
                  {r.authors.length > 2 ? " et al." : ""} ({r.year}). {r.journal ?? "—"}
                </p>
              )}
              <p className="mt-1.5 rounded-[4px] bg-marigold/35 p-2 text-[12px] leading-relaxed text-black/85">
                {c.snippet}
              </p>
              <div className="mt-2 flex items-center justify-between gap-2">
                <Button
                  variant={openCitationId === c.referenceId ? "primary" : "ghost"}
                  size="sm"
                  disabled={!r?.oaUrl}
                  onClick={() => onOpenPdf(c.referenceId, c.snippet)}
                >
                  <FileSearch size={13} /> {openCitationId === c.referenceId ? "Sedang dibuka" : "Buka PDF & sorot"}
                </Button>
                {!r?.oaUrl && <span className="text-[11px] text-black/40">tidak ada tautan teks penuh</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
