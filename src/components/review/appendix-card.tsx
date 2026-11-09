"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { Appendix } from "@/lib/types";
import { Check, ClipboardList, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

const KIND: Record<Appendix["kind"], string> = { kuesioner: "Kuesioner", wawancara: "Pedoman wawancara", validasi: "Angket validasi ahli" };

/** Draf instrumen sesuai metode penelitian. Perlu divalidasi pembimbing/ahli sebelum dipakai mengumpulkan data. */
export function AppendixCard() {
  const project = useProject((s) => s.project);
  const setPart = useProject((s) => s.setPart);
  const [items, setItems] = useState<Appendix[]>(project?.appendices ?? []);
  const [busy, setBusy] = useState<"gen" | "save" | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    setItems(project?.appendices ?? []);
  }, [project?.id, project?.appendices]);

  if (!project) return null;
  const edit = (i: number, patch: Partial<Appendix>) => {
    setMsg(null);
    setItems((a) => a.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  };

  const generate = async () => {
    setBusy("gen");
    setMsg(null);
    try {
      const r = await api.generateAppendices(project.id);
      setPart({ appendices: r.appendices });
      setMsg({ ok: true, text: `${r.appendices.length} lampiran dibuat oleh ${r.provider}.` });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal membuat" });
    } finally {
      setBusy(null);
    }
  };
  const save = async (next = items) => {
    setBusy("save");
    try {
      const saved = await api.saveAppendices(project.id, next);
      setPart({ appendices: saved });
      setMsg({ ok: true, text: "Tersimpan. Akan masuk ke bagian Lampiran di .docx." });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal menyimpan" });
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">
          <ClipboardList size={12} /> Lampiran
        </Pill>
        <Pill>{project.appendices.length} instrumen</Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Instrumen penelitian</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Draf kuesioner atau pedoman wawancara menurut metode dan variabel Anda. Ini rancangan instrumen, bukan data: validasikan ke pembimbing sebelum dipakai.
      </p>
      <div className="mt-4">
        <Button onClick={generate} loading={busy === "gen"} disabled={busy !== null}>
          {busy !== "gen" && <Sparkles size={15} />} {items.length ? "Buat ulang" : "Buat instrumen"}
        </Button>
      </div>
      {msg && <p className={msg.ok ? "mt-3 text-[13px] text-[#0a5f1e]" : "mt-3 text-[13px] text-vermillion"}>{msg.text}</p>}

      <div className="mt-4 space-y-5">
        {items.map((a, i) => (
          <div key={a.id} className="rounded-card border border-hairline p-3">
            <div className="flex items-center gap-2">
              <Pill tone="sky">{KIND[a.kind]}</Pill>
              <Input aria-label="Judul lampiran" value={a.title} onChange={(e) => edit(i, { title: e.target.value })} />
              <Button variant="danger" size="sm" aria-label="Hapus lampiran" onClick={() => void save(items.filter((_, j) => j !== i))}>
                <Trash2 size={15} />
              </Button>
            </div>
            <Textarea aria-label="Pengantar" className="mt-2" rows={3} value={a.intro} onChange={(e) => edit(i, { intro: e.target.value })} />
            <Textarea
              aria-label="Butir (satu per baris)"
              className="mt-2"
              rows={Math.min(14, a.items.length + 1)}
              value={a.items.join("\n")}
              onChange={(e) => edit(i, { items: e.target.value.split("\n") })}
            />
            <p className="mt-1 text-[11.5px] text-black/40">Satu butir per baris · {a.items.filter((x) => x.trim()).length} butir</p>
          </div>
        ))}
        {items.length > 0 && (
          <Button variant="ghost" onClick={() => void save()} loading={busy === "save"} disabled={busy !== null}>
            {busy !== "save" && <Check size={15} />} Simpan sunting
          </Button>
        )}
      </div>
    </Card>
  );
}
