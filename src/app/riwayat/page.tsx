"use client";

import { askConfirm } from "@/components/ui/confirm";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import { DOMAIN_LABEL, METHOD_LABEL, type ProjectSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BookMarked, ChartNetwork, FilePlus2, FileText, History, Loader2, Table2, Trash2, Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const fmt = (n: number) => n.toLocaleString("id-ID");

function when(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "baru saja";
  if (mins < 60) return `${mins} menit lalu`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)} jam lalu`;
  if (mins < 60 * 24 * 7) return `${Math.round(mins / 60 / 24)} hari lalu`;
  return new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "long", year: "numeric" }).format(d);
}

/** Langkah wizard yang paling masuk akal untuk melanjutkan proyek ini. */
function resumeStep(p: ProjectSummary): { href: string; label: string } {
  if (p.review.advisor !== null || p.review.guardrail !== null) return { href: "/proyek/6-review", label: "Review & ekspor" };
  if (p.sections_filled > 0 || p.refs_selected > 0) return { href: "/proyek/4-draf", label: "Draf" };
  return { href: "/proyek/2-judul", label: "Judul" };
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-[12px] text-black/50">{label}</p>
      <p className="mt-1 text-[26px] font-bold tracking-tight text-black/90">{value}</p>
      {hint && <p className="text-[11.5px] text-black/40">{hint}</p>}
    </Card>
  );
}

function Score({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null;
  return <Pill tone={value >= 75 ? "green" : value >= 50 ? "yellow" : "coral"}>{label} {value}</Pill>;
}

export default function RiwayatPage() {
  const router = useRouter();
  const activeId = useProject((s) => s.activeId);
  const openProject = useProject((s) => s.openProject);
  const closeProject = useProject((s) => s.closeProject);

  const [rows, setRows] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listProjects()
      .then((r) => {
        setRows(r);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Gagal memuat riwayat"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const open = (p: ProjectSummary) => {
    openProject(p.thesis_id);
    router.push(resumeStep(p).href);
  };

  const remove = async (p: ProjectSummary) => {
    if (!(await askConfirm(`Hapus proyek "${p.title.slice(0, 80)}"? Semua draf, rujukan, dan riwayat versinya ikut terhapus dan tidak bisa dikembalikan.`, { danger: true }))) return;
    setBusyId(p.thesis_id);
    try {
      await api.deleteThesis(p.thesis_id);
      if (p.thesis_id === activeId) closeProject();
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menghapus proyek");
    } finally {
      setBusyId(null);
    }
  };

  const totalWords = rows?.reduce((a, r) => a + r.words, 0) ?? 0;
  const totalRevisions = rows?.reduce((a, r) => a + r.revisions, 0) ?? 0;
  const reviewed = rows?.filter((r) => r.review.advisor !== null || r.review.guardrail !== null).length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-widest text-brand">
            <History size={14} /> Riwayat
          </p>
          <h1 className="t-heading mt-1">Proyek skripsi Anda</h1>
          <p className="mt-1 text-[13.5px] text-graphite">Semua proyek tersimpan di akun ini. Buka untuk melanjutkan tepat di langkah terakhir.</p>
        </div>
        <Button
          onClick={() => {
            closeProject();
            router.push("/proyek/1-inisiasi");
          }}
        >
          <FilePlus2 size={15} /> Proyek baru
        </Button>
      </div>

      {error && <p className="text-[13px] text-vermillion">{error}</p>}

      {rows === null && !error && (
        <p className="flex items-center gap-2 text-[13px] text-black/50">
          <Loader2 size={15} className="animate-spin" /> Memuat riwayat…
        </p>
      )}

      {rows && rows.length === 0 && (
        <Card className="border-dashed text-center">
          <p className="text-[14px] font-medium">Belum ada proyek.</p>
          <p className="mt-1 text-[13px] text-black/50">Mulai dari awal atau lanjutkan judul dan bab yang sudah Anda tulis.</p>
          <div className="mt-4">
            <Button onClick={() => router.push("/proyek/1-inisiasi")}>Mulai proyek pertama</Button>
          </div>
        </Card>
      )}

      {rows && rows.length > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Proyek" value={fmt(rows.length)} />
            <Stat label="Kata ditulis" value={fmt(totalWords)} hint="di seluruh proyek" />
            <Stat label="Sudah di-review" value={`${reviewed}/${rows.length}`} hint="Advisor atau Guardrail" />
            <Stat label="Revisi tersimpan" value={fmt(totalRevisions)} hint="versi lama yang bisa diurungkan" />
          </div>

          <ol className="space-y-3">
            {rows.map((p) => {
              const pct = Math.min(100, Math.round((p.words / Math.max(p.target_words, 1)) * 100));
              const step = resumeStep(p);
              const isActive = p.thesis_id === activeId;
              return (
                <li key={p.thesis_id}>
                  <Card className={cn("transition-colors", isActive && "border-brand/50")}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {isActive && <Pill tone="blue">Sedang dibuka</Pill>}
                          <Pill tone={p.source_mode === "EXISTING" ? "coral" : "basic"}>{p.source_mode === "EXISTING" ? "Naskah sendiri" : "Dari awal"}</Pill>
                          <Pill>{METHOD_LABEL[p.method]} · {p.degree_level}</Pill>
                          <Pill>{DOMAIN_LABEL[p.domain]}</Pill>
                          <Score label="Pembimbing" value={p.review.advisor} />
                          <Score label="Guardrail" value={p.review.guardrail} />
                        </div>
                        <h2 className="mt-2 text-[16px] font-semibold leading-snug text-black/90">{p.title}</h2>
                        <p className="mt-0.5 text-[12px] text-black/45">
                          Terakhir diubah {when(p.updated_at)} · dibuat {when(p.created_at)}
                        </p>
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" onClick={() => open(p)}>
                          Lanjutkan: {step.label}
                        </Button>
                        <Button size="sm" variant="text" onClick={() => remove(p)} disabled={busyId === p.thesis_id} aria-label={`Hapus proyek ${p.title}`}>
                          {busyId === p.thesis_id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                        </Button>
                      </div>
                    </div>

                    <div className="mt-4">
                      <div className="flex justify-between text-[12px] text-black/55">
                        <span>
                          {p.sections_filled}/{p.sections_total} subbab terisi
                        </span>
                        <span>
                          {fmt(p.words)} / {fmt(p.target_words)} kata ({pct}%)
                        </span>
                      </div>
                      <div className="mt-1 h-2 overflow-hidden rounded-pill bg-black/8">
                        <div className="h-full rounded-pill bg-brand" style={{ width: `${pct}%` }} />
                      </div>
                    </div>

                    <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-black/60">
                      <div className="flex items-center gap-1.5"><BookMarked size={13} /> {p.refs_selected} rujukan</div>
                      <div className="flex items-center gap-1.5"><ChartNetwork size={13} /> {p.charts} grafik/diagram</div>
                      <div className="flex items-center gap-1.5"><Table2 size={13} /> {p.tables} tabel</div>
                      {p.sections_imported > 0 && <div className="flex items-center gap-1.5"><FileText size={13} /> {p.sections_imported} subbab tulisan Anda</div>}
                      {p.revisions > 0 && <div className="flex items-center gap-1.5"><Undo2 size={13} /> {p.revisions} revisi tersimpan</div>}
                    </dl>
                  </Card>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </div>
  );
}
