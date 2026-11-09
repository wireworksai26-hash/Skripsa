"use client";

import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { useProject } from "@/lib/store";
import { AlertTriangle, ArrowRight, Check, Loader2, RefreshCw, Wand2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { TitleOption } from "@/lib/types";

export default function JudulPage() {
  const router = useRouter();
  const project = useProject((s) => s.project);
  const titles = project?.titles ?? [];
  const generateTitles = useProject((s) => s.generateTitles);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!project) router.replace("/proyek/1-inisiasi");
  }, [project, router]);

  const run = async () => {
    if (!project) return;
    setLoading(true);
    setError(null);
    try {
      await generateTitles();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membuat judul");
    } finally {
      setLoading(false);
    }
  };

  if (!project) return null;

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="yellow">
            <Wand2 size={12} /> Title & Ideation Engine
          </Pill>
          {project.titlesProvider && <Pill tone="midnight">Ditulis oleh {project.titlesProvider}</Pill>}
        </div>
        <h1 className="t-heading mt-4">Pilih judul & analisis celah penelitian</h1>
        <p className="t-serif-lede mt-2 text-graphite">
          Generator menghasilkan opsi judul spesifik dengan analisis celah. Analisis gap diperdalam pada
          Langkah 3 setelah artikel jurnal nyata ditarik dari basis data ilmiah.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button onClick={run} disabled={loading}>
            {loading ? <Loader2 size={16} className="animate-spin" /> : titles.length ? <RefreshCw size={15} /> : <Wand2 size={15} />}
            {titles.length ? "Buat ulang 5 judul" : "Buat 5 opsi judul"}
          </Button>
          {titles.length > 0 && (
            <Button variant="ghost" disabled={!project.pickedTitleId} onClick={() => router.push("/proyek/3-rujukan")}>
              Lanjut ke Rujukan <ArrowRight size={15} />
            </Button>
          )}
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-btn border border-vermillion/30 bg-vermillion/5 p-3 text-[13px] text-vermillion">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </Card>

      {loading && (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-card border border-hairline bg-white" />
          ))}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {titles.map((t: TitleOption) => <TitleCard key={t.id} title={t} />)}
      </div>

      {titles.length > 0 && !project.pickedTitleId && (
        <Card className="border-dashed text-center">
          <p className="text-[13px] text-black/55">Klik salah satu kartu judul untuk mengunci, lalu lanjut ke tarikan rujukan.</p>
          <div className="mt-3">
            <ButtonLink variant="outline" href="/proyek/3-rujukan">
              Lewati, pilih rujukan dulu
            </ButtonLink>
          </div>
        </Card>
      )}

      {project.pickedTitleId && (
        <Card className="border-brand/40 bg-sky-tint">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[12px] font-medium uppercase tracking-wide text-brand">Judul terkunci</p>
              <p className="mt-1 font-semibold text-black/95">
                {titles.find((t) => t.id === project.pickedTitleId)?.text}
              </p>
            </div>
            <Button variant="primary" onClick={() => router.push("/proyek/3-rujukan")}>
              Tarik rujukan <ArrowRight size={15} />
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function TitleCard({ title }: { title: TitleOption }) {
  const project = useProject((s) => s.project);
  const pickTitle = useProject((s) => s.pickTitle);
  const [failed, setFailed] = useState<string | null>(null);
  const picked = project?.pickedTitleId === title.id;

  return (
    <button
      type="button"
      onClick={() => {
        setFailed(null);
        pickTitle(title.id).catch((e) => setFailed(e instanceof Error ? e.message : "Gagal menyimpan pilihan"));
      }}
      className={`rounded-card border p-5 text-left transition-colors duration-200 ${
        picked
          ? "border-brand bg-sky-tint"
          : "border-hairline bg-white hover:bg-black/[0.03] duration-200"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="t-heading-sm">{title.text}</h3>
        <span
          className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full border ${
            picked ? "border-brand bg-brand text-white" : "border-black/20"
          }`}
        >
          {picked && <Check size={13} strokeWidth={3} />}
        </span>
      </div>
      {title.rationale && (
        <p className="mt-2 text-[13px] leading-relaxed text-black/60">{title.rationale}</p>
      )}
      {title.gap && (
        <p className="mt-2 text-[13px] leading-relaxed text-graphite">
          <span className="font-medium text-black/80">Gap: </span>
          {title.gap}
        </p>
      )}
      {failed && <p className="mt-2 text-[12px] text-vermillion">{failed}</p>}
    </button>
  );
}
