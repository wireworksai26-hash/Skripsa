"use client";

import { Button } from "@/components/ui/button";
import { Card, AccentCard } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { AppendixCard } from "@/components/review/appendix-card";
import { DefenseCard } from "@/components/review/defense-card";
import { SlidesCard } from "@/components/review/slides-card";
import { CitationAuditCard } from "@/components/review/citation-audit-card";
import { IntegrityCard } from "@/components/review/integrity-card";
import { FrontMatterCard } from "@/components/review/frontmatter-card";
import { ShareCard } from "@/components/review/share-card";
import { SimilarityCard } from "@/components/review/similarity-card";
import { BibliographyCard } from "@/components/review/bibliography-card";
import { RevisePanel } from "@/components/review/revise-panel";
import { missingCoverFields } from "@/lib/cover";
import { useProfile, useProject } from "@/lib/store";
import Link from "next/link";
import type { AgentNote } from "@/lib/types";
import { cn, countWords } from "@/lib/utils";
import {
  BadgeCheck,
  Download,
  FileCheck2,
  GraduationCap,
  Loader2,
  Stamp,
  TriangleAlert,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { AgentReview } from "@/lib/types";

export default function ReviewPage() {
  const router = useRouter();
  const project = useProject((s) => s.project);
  const runReview = useProject((s) => s.runReview);
  const profile = useProfile((s) => s.profile);
  const loadProfile = useProfile((s) => s.load);

  const [running, setRunning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [numbering, setNumbering] = useState<"decimal" | "alpha">("decimal");
  const [includeEmpty, setIncludeEmpty] = useState(false);
  const [exportName, setExportName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProfile().catch(() => undefined);
  }, [loadProfile]);

  useEffect(() => {
    if (!project) router.replace("/proyek/1-inisiasi");
  }, [project, router]);

  if (!project) return null;

  const advisor = project.reviews.find((r) => r.agent === "ADVISOR");
  const examiner = project.reviews.find((r) => r.agent === "EXAMINER");
  const guardrail = project.reviews.find((r) => r.agent === "GUARDRAIL");

  const runAll = async () => {
    if (!project) return;
    setRunning(true);
    setError(null);
    try {
      await runReview();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Panel review gagal");
    } finally {
      setRunning(false);
    }
  };

  const doExport = async () => {
    if (!project) return;
    setExporting(true);
    try {
      const { exportDocx } = await import("@/lib/export-docx");
      const name = await exportDocx(project, { numbering, profile, includeEmpty });
      setExportName(name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ekspor gagal");
    } finally {
      setExporting(false);
    }
  };

  const filled = project.sections.filter((s) => countWords(s.content) > 0).length;
  const emptyChapters = Array.from(new Set(project.sections.map((s) => s.chapterCode))).filter(
    (c) => !project.sections.some((s) => s.chapterCode === c && countWords(s.content) > 0)
  );
  const doneCount = [advisor, examiner, guardrail].filter((r) => r?.done).length;

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="midnight">
            <Stamp size={12} /> Multi-Agent Review
          </Pill>
          <Pill>{doneCount}/3 agen menilai</Pill>
        </div>
        <h1 className="t-heading mt-4">Review Dosen Pembimbing, Penguji &amp; Guardrail</h1>
        <p className="t-serif-lede mt-2 text-graphite">
          Advisor Agent menilai logika dan kebaruan; Examiner Agent menyusun simulasi pertanyaan
          sidang; Quality Guardrail menghitung target kata dan menguji kesiapan tautan DOI.
        </p>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center [&>button]:w-full sm:[&>button]:w-auto">
          <Button onClick={runAll} disabled={running}>
            {running ? <Loader2 size={15} className="animate-spin" /> : <BadgeCheck size={15} />}
            Jalankan panel review
          </Button>
          <label className="flex items-center gap-2 text-[13px] text-black/65">
            Penomoran subbab
            <select
              className="select-chevron min-h-10 appearance-none rounded-btn border border-hairline bg-white py-1.5 pl-3 pr-9 text-base sm:min-h-0 sm:px-2 sm:text-[13px]"
              value={numbering}
              onChange={(e) => setNumbering(e.target.value as "decimal" | "alpha")}
            >
              <option value="decimal">1.1, 1.2</option>
              <option value="alpha">A., B., C.</option>
            </select>
          </label>
          <Button variant="ghost" onClick={doExport} disabled={exporting}>
            {exporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            Ekspor draf .docx
          </Button>
          <Button variant="text" onClick={() => router.push("/proyek/4-draf")}>
            Kembali menyunting draf
          </Button>
        </div>
        <p className="mt-3 text-[13px] text-black/60">
          Ekspor bisa dilakukan kapan saja: {filled} dari {project.sections.length} subbab sudah terisi
          {emptyChapters.length > 0 ? `; bab ${emptyChapters.join(", ")} belum ditulis dan dilewati.` : "."}
        </p>
        {emptyChapters.length > 0 && (
          <label className="mt-2 flex min-h-10 cursor-pointer items-center gap-2 text-[13px] text-black/70">
            <input type="checkbox" checked={includeEmpty} onChange={(e) => setIncludeEmpty(e.target.checked)} />
            Sertakan bab yang belum ditulis sebagai judul kosong
          </label>
        )}
        {profile && missingCoverFields(profile).length > 0 && (
          <p className="mt-3 text-[12.5px] text-black/55">
            Sampul memuat garis isian kosong untuk: {missingCoverFields(profile).join(", ")}.{" "}
            <Link href="/profil" className="font-medium text-brand underline underline-offset-2">
              Lengkapi profil
            </Link>
          </p>
        )}
        {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}
        {exportName && (
          <p className="mt-3 flex items-center gap-1.5 text-[13px] text-graphite">
            <FileCheck2 size={14} className="text-brand" /> Berhasil diunduh: <strong>{exportName}</strong>
            <span className="text-black/45">· Di Word, pilih Ya saat diminta memperbarui bidang agar daftar isi dan nomor halaman terisi.</span>
          </p>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <AgentCard
          title="Advisor Agent"
          persona="Dosen Pembimbing"
          icon={<GraduationCap size={18} />}
          review={advisor}
          tone="coral"
        />
        <AgentCard
          title="Examiner Agent"
          persona="Dosen Penguji"
          icon={<TriangleAlert size={18} />}
          review={examiner}
          tone="saffron"
        />
        <AgentCard
          title="Quality Guardrail"
          persona="Validator"
          icon={<Stamp size={18} />}
          review={guardrail}
          tone="sky"
        />
        <AccentCard tone="midnight">
          <h3 className="t-heading-sm">Disclaimer etika akademik</h3>
          <p className="mt-2 text-[13px] leading-relaxed text-white/80">
            Draf dihasilkan sebagai <strong>asistensi draf awal</strong> dan media bimbingan — bukan
            layanan joki skripsi. Draf wajib dievaluasi, ditulis ulang memakai pemikiran kritis Anda,
            dan dikonsultasikan bersama Dosen Pembimbing.
          </p>
          <p className="mt-3 text-[12px] text-white/60">
            Draf tersimpan di akun Anda pada server SkripsiAI. Isi draf dikirim ke penyedia LLM yang
            dikonfigurasi di backend untuk proses penulisan.
          </p>
        </AccentCard>
      </div>

      <RevisePanel key={project.reviews.map((r) => `${r.agent}${r.done}${r.notes.length}`).join()} project={project} />

      <div className="grid gap-6 lg:grid-cols-2">
        <DefenseCard />
        <SimilarityCard />
      </div>

      <FrontMatterCard />

      <AppendixCard />

      <SlidesCard />

      <ShareCard />

      <BibliographyCard project={project} />

      <CitationAuditCard />

      <IntegrityCard />
    </div>
  );
}

function AgentCard({
  title,
  persona,
  icon,
  review,
  tone,
}: {
  title: string;
  persona: string;
  icon: React.ReactNode;
  review?: AgentReview;
  tone: "coral" | "saffron" | "sky";
}) {
  const toneCls: Record<string, string> = {
    coral: "bg-coral/10",
    saffron: "bg-saffron/10",
    sky: "bg-sky-tint",
  };

  return (
    <Card className={cn(toneCls[tone])}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-pill border-2 border-black/15 bg-white">
            {icon}
          </span>
          <div>
            <h3 className="font-bold text-black/95">{title}</h3>
            <p className="text-[12px] text-black/50">{persona}</p>
          </div>
        </div>
        {review?.done && typeof review.score === "number" && (
          <Pill tone={review.score >= 75 ? "green" : review.score >= 50 ? "yellow" : "coral"}>
            Skor {review.score}
          </Pill>
        )}
      </div>
      {review?.done && review.breakdown && review.breakdown.length > 0 && (
        <div className="mt-4 space-y-1.5 rounded-btn border border-black/10 bg-white/70 p-3">
          {review.breakdown.map((b) => (
            <div key={b.key} title={b.detail}>
              <div className="flex items-baseline justify-between gap-2 text-[12px] text-black/70">
                <span>{b.label}</span>
                <span className="tabular-nums">
                  {b.points}/{b.max}
                </span>
              </div>
              <div className="mt-0.5 h-1.5 overflow-hidden rounded-pill bg-black/10">
                <div
                  className={cn("h-full", b.points / b.max >= 0.75 ? "bg-[#2e9d4d]" : b.points / b.max >= 0.5 ? "bg-saffron" : "bg-vermillion")}
                  style={{ width: `${Math.round((b.points / b.max) * 100)}%` }}
                />
              </div>
              <p className="mt-0.5 text-[11px] text-black/45">{b.detail}</p>
            </div>
          ))}
        </div>
      )}
      <ul className="mt-4 space-y-2.5">
        {review?.done || (review && review.notes.length > 0) ? (
          review.notes.map((n: AgentNote, i: number) => (
            <li
              key={i}
              className={cn(
                "rounded-btn border p-3 text-[13px] leading-relaxed whitespace-pre-line",
                n.kind === "praise"
                  ? "border-[#8ed78c]/50 bg-[#f0faf0] text-[#0a4d1e]"
                  : n.kind === "warn"
                    ? "border-saffron/40 bg-saffron/5 text-[#6b4a00]"
                    : n.kind === "fix"
                      ? "border-vermillion/40 bg-vermillion/5 text-vermillion"
                      : "border-black/10 bg-white text-graphite"
              )}
            >
              {n.text}
            </li>
          ))
        ) : (
          <li className="rounded-btn border border-dashed border-black/15 bg-white/60 p-4 text-center text-[13px] text-black/45">
            Belum dinilai — jalankan panel review.
          </li>
        )}
      </ul>
    </Card>
  );
}
