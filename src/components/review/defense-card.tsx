"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { DefenseResult } from "@/lib/types";
import { MessageSquareQuote, Send } from "lucide-react";
import { useMemo, useState } from "react";

/** Ambil pertanyaan dari catatan Examiner: P1 · Fokus — "pertanyaan"\nSaran jawaban: ... */
function questionsOf(notes: Array<{ text: string }>): string[] {
  return notes.map((n) => /—\s*"([\s\S]+?)"\s*(?:\n|$)/.exec(n.text)?.[1]?.trim()).filter((q): q is string => !!q);
}

export function DefenseCard() {
  const project = useProject((s) => s.project);
  const examiner = project?.reviews.find((r) => r.agent === "EXAMINER");
  const questions = useMemo(() => (examiner?.done ? questionsOf(examiner.notes) : []), [examiner]);
  const [qi, setQi] = useState(0);
  const [custom, setCustom] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DefenseResult | null>(null);

  if (!project) return null;
  const question = (custom.trim() || questions[qi]) ?? "";

  const submit = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.evaluateDefense(project.id, question, answer));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menilai");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="coral">
          <MessageSquareQuote size={12} /> Latihan sidang
        </Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Jawab pertanyaan penguji</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Pilih pertanyaan dari Examiner (atau tulis sendiri), jawab seperti di ruang sidang, lalu dinilai dengan rubrik ketat. Skor tinggi butuh jawaban yang bersandar pada draf Anda.
      </p>

      <div className="mt-4 grid gap-3">
        {questions.length > 0 && (
          <div>
            <Label htmlFor="dq">Pertanyaan dari Examiner</Label>
            <Select id="dq" value={qi} onChange={(e) => (setQi(Number(e.target.value)), setCustom(""))}>
              {questions.map((q, i) => (
                <option key={i} value={i}>
                  P{i + 1} · {q.slice(0, 80)}
                </option>
              ))}
            </Select>
          </div>
        )}
        <div>
          <Label htmlFor="dc">{questions.length ? "Atau pertanyaan Anda sendiri" : "Pertanyaan (jalankan panel review untuk mendapat pertanyaan Examiner)"}</Label>
          <Textarea id="dc" rows={2} value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="Mis. Mengapa metode kuantitatif dipilih, bukan kualitatif?" />
        </div>
        {question && <p className="rounded-btn bg-sky-tint p-3 text-[13.5px] font-medium text-black/85">{question}</p>}
        <div>
          <Label htmlFor="da">Jawaban Anda</Label>
          <Textarea id="da" rows={6} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Jawab 3-6 kalimat, sebut dasar dari draf atau rujukan Anda." />
        </div>
        <div>
          <Button onClick={submit} loading={busy} disabled={busy || question.trim().length < 10 || answer.trim().length < 5}>
            {!busy && <Send size={15} />} Nilai jawaban saya
          </Button>
        </div>
      </div>
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}

      {result && (
        <div className="mt-5 space-y-3 text-[13.5px]">
          <div className="flex items-center gap-2">
            <Pill tone={result.score >= 75 ? "green" : result.score >= 50 ? "yellow" : "coral"}>Skor {result.score}</Pill>
            <span className="text-[12px] text-black/45">dinilai oleh {result.provider}</span>
          </div>
          <ul className="space-y-1.5">
            {result.dimensions.map((d) => (
              <li key={d.key} className="rounded-btn border border-hairline p-2.5">
                <span className="font-medium">{d.label}</span> <span className="text-black/55">{d.score}/{d.max}{d.verified ? "" : " · bukti tidak terverifikasi"}</span>
                {d.critique && <p className="mt-0.5 text-black/70">{d.critique}</p>}
              </li>
            ))}
          </ul>
          {result.strength && <p className="rounded-btn bg-[#f0faf0] p-2.5 text-[#0a4d1e]">Kekuatan: {result.strength}</p>}
          {result.improvements.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-vermillion">
              {result.improvements.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          )}
          {result.betterAnswer && (
            <div className="rounded-btn border border-dashed border-hairline-strong p-3">
              <p className="text-[12px] font-medium text-black/50">Contoh jawaban yang lebih kuat (berdasarkan draf Anda)</p>
              <p className="mt-1">{result.betterAnswer}</p>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
