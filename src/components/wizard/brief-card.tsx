"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { BriefFields, briefFilled, EMPTY_BRIEF } from "@/components/wizard/brief-fields";
import { useProject } from "@/lib/store";
import type { Brief } from "@/lib/types";
import { Check, Compass } from "lucide-react";
import { useEffect, useState } from "react";

/** Kerangka penelitian dari peneliti pada proyek yang sudah dibuat: bisa dilihat dan disunting kapan saja. */
export function BriefCard() {
  const project = useProject((s) => s.project);
  const updateBrief = useProject((s) => s.updateBrief);
  const [form, setForm] = useState<Brief>(project?.brief ?? EMPTY_BRIEF);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    setForm(project?.brief ?? EMPTY_BRIEF);
  }, [project?.id, project?.brief]);

  if (!project) return null;
  const has = briefFilled(project.brief);

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await updateBrief(form);
      setMsg({ ok: true, text: "Tersimpan. Subbab yang dibuat setelah ini mengikuti kerangka Anda; subbab lama perlu dibuat ulang." });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal menyimpan" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">
          <Compass size={12} /> Kerangka penelitian
        </Pill>
        {has ? <Pill tone="green">Dipakai penulis</Pill> : <Pill>Belum diisi</Pill>}
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-graphite">
        Topik, fenomena, research problem, teori, dan metode yang sudah Anda temukan. Penulis mengembangkannya per bab dan tidak menggantinya.
      </p>
      {!open ? (
        <Button className="mt-3" variant="ghost" onClick={() => setOpen(true)}>
          {has ? "Lihat dan sunting kerangka" : "Isi kerangka penelitian"}
        </Button>
      ) : (
        <div className="mt-4 space-y-4">
          <BriefFields value={form} onChange={(b) => (setMsg(null), setForm(b))} idPrefix="card-brief" />
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={save} loading={busy}>
              {!busy && <Check size={15} />} Simpan kerangka
            </Button>
            <Button variant="text" onClick={() => setOpen(false)} disabled={busy}>
              Tutup
            </Button>
            {msg && <span className={msg.ok ? "text-[13px] text-[#0a5f1e]" : "text-[13px] text-vermillion"}>{msg.text}</span>}
          </div>
        </div>
      )}
    </Card>
  );
}
