"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { FrontMatter } from "@/lib/types";
import { Check, FileText, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

const EMPTY: FrontMatter = { abstractId: "", abstractEn: "", keywordsId: [], keywordsEn: [], preface: "" };
const kw = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 5);

/** Abstrak ID+EN, kata kunci, dan kata pengantar dibuat dari draf. Angka yang tidak ada di draf ditolak server. */
export function FrontMatterCard() {
  const project = useProject((s) => s.project);
  const setPart = useProject((s) => s.setPart);
  const [form, setForm] = useState<FrontMatter>(project?.front ?? EMPTY);
  const [busy, setBusy] = useState<"gen" | "save" | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    setForm(project?.front ?? EMPTY);
  }, [project?.id, project?.front]);

  if (!project) return null;
  const set = <K extends keyof FrontMatter>(k: K, v: FrontMatter[K]) => {
    setMsg(null);
    setForm((f) => ({ ...f, [k]: v }));
  };
  const hasPlaceholder = /\[DATA/i.test(form.abstractId + form.abstractEn);

  const generate = async () => {
    setBusy("gen");
    setMsg(null);
    try {
      const r = await api.generateFront(project.id);
      setPart({ front: r.front });
      setMsg({ ok: true, text: `Dibuat oleh ${r.provider}. Periksa dan sunting sebelum dipakai.` });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal membuat" });
    } finally {
      setBusy(null);
    }
  };
  const save = async () => {
    setBusy("save");
    try {
      await api.saveFront(project.id, form);
      setPart({ front: form });
      setMsg({ ok: true, text: "Tersimpan. Akan masuk ke berkas .docx." });
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
          <FileText size={12} /> Halaman depan
        </Pill>
        {project.front ? <Pill tone="green">Ada di ekspor</Pill> : <Pill>Belum dibuat</Pill>}
      </div>
      <h2 className="t-heading-sm mt-3">Abstrak, kata kunci, dan kata pengantar</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Dibuat dari draf Anda saja. Bila hasil penelitian belum ada, tempatnya diisi penanda <span className="rounded-[3px] bg-marigold/40 px-0.5">[DATA: …]</span>, bukan angka karangan.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={generate} loading={busy === "gen"} disabled={busy !== null}>
          {busy !== "gen" && <Sparkles size={15} />} {project.front ? "Buat ulang" : "Buat dari draf"}
        </Button>
        {(project.front || form.abstractId) && (
          <Button variant="ghost" onClick={save} loading={busy === "save"} disabled={busy !== null}>
            {busy !== "save" && <Check size={15} />} Simpan sunting
          </Button>
        )}
      </div>
      {msg && <p className={msg.ok ? "mt-3 text-[13px] text-[#0a5f1e]" : "mt-3 text-[13px] text-vermillion"}>{msg.text}</p>}

      {(project.front || form.abstractId) && (
        <div className="mt-5 grid gap-4">
          {hasPlaceholder && <p className="rounded-btn bg-marigold/25 p-2.5 text-[12.5px] text-black/75">Abstrak memuat penanda [DATA]. Ganti dengan temuan sebenarnya setelah data terkumpul.</p>}
          <div>
            <Label htmlFor="absid">Abstrak (Indonesia)</Label>
            <Textarea id="absid" rows={7} value={form.abstractId} onChange={(e) => set("abstractId", e.target.value)} />
            <Label htmlFor="kwid" className="mt-2">Kata kunci (pisahkan koma)</Label>
            <Input id="kwid" value={form.keywordsId.join(", ")} onChange={(e) => set("keywordsId", kw(e.target.value))} />
          </div>
          <div>
            <Label htmlFor="absen">Abstract (English)</Label>
            <Textarea id="absen" rows={7} value={form.abstractEn} onChange={(e) => set("abstractEn", e.target.value)} />
            <Label htmlFor="kwen" className="mt-2">Keywords</Label>
            <Input id="kwen" value={form.keywordsEn.join(", ")} onChange={(e) => set("keywordsEn", kw(e.target.value))} />
          </div>
          <div>
            <Label htmlFor="pref">Kata pengantar</Label>
            <Textarea id="pref" rows={9} value={form.preface} onChange={(e) => set("preface", e.target.value)} />
          </div>
        </div>
      )}
    </Card>
  );
}
