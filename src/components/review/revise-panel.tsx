"use client";

import { askConfirm } from "@/components/ui/confirm";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { useProject } from "@/lib/store";
import type { ReviseResult, ThesisProject } from "@/lib/types";
import { countWords, cn } from "@/lib/utils";
import { AlertTriangle, Loader2, Undo2, Wrench } from "lucide-react";
import { useMemo, useState } from "react";

interface Item {
  id: string;
  agent: string;
  kind: string;
  text: string;
}

const MAX_ITEMS = 14;
const AGENT_LABEL: Record<string, string> = { ADVISOR: "Pembimbing", EXAMINER: "Penguji", GUARDRAIL: "Guardrail" };

/** Kode subbab (mis. 1.2) yang disebut di sebuah catatan review. */
function mentioned(text: string, codes: Set<string>): string[] {
  return [...new Set([...text.matchAll(/(?<![\d.])(\d{1,2}\.\d{1,2})(?![\d.])/g)].map((m) => m[1]).filter((c) => codes.has(c)))];
}

export function RevisePanel({ project }: { project: ThesisProject }) {
  const reviseSection = useProject((s) => s.reviseSection);
  const undoSection = useProject((s) => s.undoSection);

  const items: Item[] = useMemo(
    () =>
      project.reviews.flatMap((r) =>
        r.done
          ? r.notes
              .filter((n) => n.kind !== "praise")
              .map((n, i) => ({ id: `${r.agent}-${i}`, agent: r.agent, kind: n.kind, text: n.text }))
          : []
      ),
    [project.reviews]
  );
  const writable = project.sections.filter((s) => countWords(s.content) >= 10);
  const codes = useMemo(() => new Set(writable.map((s) => s.sectionCode)), [writable]);

  const [checked, setChecked] = useState<Set<string>>(() => new Set(items.filter((i) => i.kind === "warn" || i.kind === "fix").map((i) => i.id)));
  const [targets, setTargets] = useState<Set<string>>(() => {
    const picked = items.filter((i) => i.kind === "warn" || i.kind === "fix").flatMap((i) => mentioned(i.text, codes));
    return new Set(picked);
  });
  const [extra, setExtra] = useState("");
  const [allowImported, setAllowImported] = useState(false);
  const [running, setRunning] = useState<{ code: string; done: number; total: number } | null>(null);
  const [results, setResults] = useState<Record<string, ReviseResult | { error: string } | { undone: true }>>({});

  const toggle = (set: Set<string>, id: string, apply: (s: Set<string>) => void) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    apply(next);
  };

  const feedback = [
    ...items.filter((i) => checked.has(i.id)).map((i) => `[${AGENT_LABEL[i.agent] ?? i.agent}] ${i.text}`),
    ...(extra.trim() ? [`[Instruksi pengguna] ${extra.trim()}`] : []),
  ].slice(0, MAX_ITEMS);
  const chosen = writable.filter((s) => targets.has(s.sectionCode));
  const needsConsent = chosen.some((s) => s.origin === "IMPORTED");
  const canRun = !running && feedback.length > 0 && chosen.length > 0 && (!needsConsent || allowImported) && project.selectedRefIds.length > 0;

  const run = async () => {
    if (needsConsent && !(await askConfirm("Perbaikan juga akan mengubah subbab tulisan Anda sendiri. Versi lama disimpan dan bisa diurungkan. Lanjutkan?", { danger: false }))) return;
    const list = chosen;
    setResults({});
    for (let i = 0; i < list.length; i++) {
      const code = list[i].sectionCode;
      setRunning({ code, done: i, total: list.length });
      try {
        const r = await reviseSection(code, feedback, allowImported);
        setResults((prev) => ({ ...prev, [code]: r }));
      } catch (e) {
        setResults((prev) => ({ ...prev, [code]: { error: e instanceof Error ? e.message : "Perbaikan gagal" } }));
      }
    }
    setRunning(null);
  };

  const undo = async (code: string) => {
    try {
      await undoSection(code);
      setResults((prev) => ({ ...prev, [code]: { undone: true } }));
    } catch (e) {
      setResults((prev) => ({ ...prev, [code]: { error: e instanceof Error ? e.message : "Gagal mengurungkan" } }));
    }
  };

  if (items.length === 0) {
    return (
      <Card>
        <div className="flex items-center gap-2">
          <Wrench size={17} className="text-brand" />
          <h2 className="t-heading-sm">Perbaiki naskah dari hasil review</h2>
        </div>
        <p className="mt-2 text-[13px] text-black/55">Jalankan panel review dulu. Catatan dosen akan muncul di sini dan bisa diterapkan ke subbab dengan satu klik.</p>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Wrench size={17} className="text-brand" />
        <h2 className="t-heading-sm">Perbaiki naskah dari hasil review</h2>
        <Pill tone="midnight">dapat diurungkan</Pill>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-graphite">
        Pilih catatan yang ingin diterapkan dan subbab yang diperbaiki. Agen menulis ulang subbab dengan tetap bersandar pada rujukan terpilih
        (tanpa data karangan), dan versi sebelumnya disimpan. Setelah itu jalankan review lagi untuk melihat dampaknya.
      </p>

      <div className="mt-4 grid gap-5 lg:grid-cols-2">
        <div>
          <Label>1. Catatan yang diterapkan ({feedback.length}/{MAX_ITEMS})</Label>
          <ul className="scroll-thin max-h-80 space-y-2 overflow-y-auto pr-1">
            {items.map((it) => (
              <li key={it.id}>
                <label className={cn("flex cursor-pointer gap-2 rounded-btn border p-2.5 text-[12.5px] leading-relaxed", checked.has(it.id) ? "border-brand/50 bg-sky-tint" : "border-hairline bg-white")}>
                  <input type="checkbox" className="mt-1" checked={checked.has(it.id)} onChange={() => toggle(checked, it.id, setChecked)} />
                  <span>
                    <span className="mr-1.5 rounded-pill bg-black/5 px-1.5 py-0.5 text-[10.5px] font-medium text-black/55">{AGENT_LABEL[it.agent] ?? it.agent}</span>
                    <span className="line-clamp-4 text-black/80">{it.text}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-3">
            <Label htmlFor="extra">Instruksi tambahan (opsional)</Label>
            <Textarea id="extra" rows={2} value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Contoh: pertegas kebaruan penelitian dan sebutkan keterbatasan sampel." />
          </div>
        </div>

        <div>
          <Label>2. Subbab yang diperbaiki ({chosen.length})</Label>
          <ul className="scroll-thin max-h-80 space-y-1.5 overflow-y-auto pr-1">
            {writable.map((s) => {
              const res = results[s.sectionCode];
              return (
                <li key={s.sectionCode} className="rounded-btn border border-hairline bg-white p-2 text-[12.5px]">
                  <label className="flex cursor-pointer items-center gap-2">
                    <input type="checkbox" checked={targets.has(s.sectionCode)} onChange={() => toggle(targets, s.sectionCode, setTargets)} disabled={!!running} />
                    <span className="min-w-0 flex-1 truncate font-medium">
                      {s.sectionCode} {s.title}
                    </span>
                    {s.origin === "IMPORTED" && <span className="rounded-pill bg-marigold/40 px-1.5 py-0.5 text-[10.5px]">tulisan Anda</span>}
                    <span className="text-black/40">{countWords(s.content)} kata</span>
                    {running?.code === s.sectionCode && <Loader2 size={13} className="animate-spin text-brand" />}
                  </label>
                  {res && "error" in res && (
                    <p className="mt-1.5 flex items-start gap-1 text-vermillion">
                      <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {res.error}
                    </p>
                  )}
                  {res && "undone" in res && <p className="mt-1.5 text-black/50">Dikembalikan ke versi sebelumnya.</p>}
                  {res && "content" in res && (
                    <div className="mt-1.5 space-y-1 text-black/70">
                      <p>
                        {res.beforeWords} → <strong>{res.wordCount}</strong> kata · oleh {res.provider}
                      </p>
                      {res.changes.length > 0 && (
                        <ul className="ml-3 list-disc text-black/60">
                          {res.changes.map((c) => (
                            <li key={c}>{c}</li>
                          ))}
                        </ul>
                      )}
                      {res.canUndo && (
                        <Button variant="text" size="sm" onClick={() => undo(s.sectionCode)}>
                          <Undo2 size={13} /> Urungkan
                        </Button>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="mt-1.5 text-[11.5px] text-black/45">Subbab yang disebut di catatan terpilih otomatis dicentang.</p>
          {needsConsent && (
            <label className="mt-2 flex items-start gap-2 text-[12.5px] text-black/70">
              <input type="checkbox" className="mt-0.5" checked={allowImported} onChange={(e) => setAllowImported(e.target.checked)} />
              Izinkan agen memperbaiki subbab tulisan saya (versi lama tetap disimpan).
            </label>
          )}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button onClick={run} disabled={!canRun}>
          {running ? <Loader2 size={15} className="animate-spin" /> : <Wrench size={15} />}
          {running ? `Memperbaiki ${running.code} (${running.done + 1}/${running.total})…` : `Perbaiki ${chosen.length} subbab`}
        </Button>
        {project.selectedRefIds.length === 0 && <span className="text-[12.5px] text-vermillion">Pilih rujukan di Langkah 3 dulu.</span>}
        {project.selectedRefIds.length > 0 && feedback.length === 0 && <span className="text-[12.5px] text-black/45">Pilih minimal satu catatan atau tulis instruksi.</span>}
        {feedback.length > 0 && chosen.length === 0 && <span className="text-[12.5px] text-black/45">Pilih minimal satu subbab.</span>}
      </div>
    </Card>
  );
}
