"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProfile, useProject } from "@/lib/store";
import type { SlidePlanItem } from "@/lib/types";
import { Download, Presentation, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Slide sidang dari naskah: ringkasan per bab (agen), lalu tabel, grafik, dan pertanyaan Examiner yang sudah ada. */
export function SlidesCard() {
  const project = useProject((s) => s.project);
  const profile = useProfile((s) => s.profile);
  const loadProfile = useProfile((s) => s.load);
  const [plan, setPlan] = useState<SlidePlanItem[] | null>(null);
  const [provider, setProvider] = useState("");
  const [busy, setBusy] = useState<"plan" | "file" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProfile().catch(() => undefined);
  }, [loadProfile]);

  if (!project) return null;

  const makePlan = async () => {
    setBusy("plan");
    setError(null);
    try {
      const r = await api.slidePlan(project.id);
      setPlan(r.slides);
      setProvider(r.provider);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menyusun slide");
    } finally {
      setBusy(null);
    }
  };

  const edit = (i: number, bullets: string[]) => setPlan((p) => (p ? p.map((s, j) => (j === i ? { ...s, bullets } : s)) : p));

  const download = async () => {
    if (!plan) return;
    setBusy("file");
    setError(null);
    try {
      const { buildPptx } = await import("@/lib/export-pptx");
      const blob = await buildPptx(project, plan, profile);
      save(blob, "slide-sidang.pptx");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membuat berkas");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="coral">
          <Presentation size={12} /> Slide sidang
        </Pill>
        {plan && <Pill>{plan.length} slide ringkasan</Pill>}
      </div>
      <h2 className="t-heading-sm mt-3">Slide presentasi dari naskah</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Agen meringkas bab yang sudah Anda tulis menjadi poin slide (angka yang tidak ada di naskah ditolak). Tabel, grafik, diagram, dan pertanyaan Examiner yang sudah ada ikut dimasukkan. Sunting poin sebelum mengunduh .pptx.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={makePlan} loading={busy === "plan"} disabled={busy !== null}>
          {busy !== "plan" && <Sparkles size={15} />} {plan ? "Susun ulang ringkasan" : "Susun slide"}
        </Button>
        {plan && (
          <Button variant="ghost" onClick={download} loading={busy === "file"} disabled={busy !== null}>
            {busy !== "file" && <Download size={15} />} Unduh .pptx
          </Button>
        )}
      </div>
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}
      {plan && (
        <div className="mt-4 space-y-3">
          <p className="text-[12px] text-black/45">Disusun oleh {provider}. Satu poin per baris.</p>
          {plan.map((s, i) => (
            <div key={s.key} className="rounded-card border border-hairline p-3">
              <p className="text-[13.5px] font-semibold">{s.title}</p>
              <textarea
                aria-label={`Poin slide ${s.title}`}
                className="mt-1.5 w-full rounded-btn border border-hairline bg-white p-2.5 text-base leading-relaxed outline-none focus:border-brand sm:text-[13.5px]"
                rows={Math.min(8, s.bullets.length + 1)}
                value={s.bullets.join("\n")}
                onChange={(e) => edit(i, e.target.value.split("\n"))}
              />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
