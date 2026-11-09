"use client";

import { CoverPreview } from "@/components/cover/cover-preview";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldHint, Input, Label, Select } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { coverInputOf, missingCoverFields, resolveCover } from "@/lib/cover";
import { useProfile, useProject } from "@/lib/store";
import type { CoverOptions } from "@/lib/types";
import { Check, Loader2, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

/** Opsi sampul per proyek + pratinjau. Identitas penulis ada di profil akun. */
export function CoverCard() {
  const project = useProject((s) => s.project);
  const updateCover = useProject((s) => s.updateCover);
  const profile = useProfile((s) => s.profile);
  const loadProfile = useProfile((s) => s.load);

  const [form, setForm] = useState<CoverOptions | null>(project?.cover ?? null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    loadProfile().catch(() => undefined);
  }, [loadProfile]);
  useEffect(() => {
    if (project) setForm(project.cover);
  }, [project?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!project || !form) return null;
  const set = <K extends keyof CoverOptions>(k: K, v: CoverOptions[K]) => {
    setMsg(null);
    setForm((f) => (f ? { ...f, [k]: v } : f));
  };
  const title = project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? project.form.topic;
  const model = resolveCover({ ...coverInputOf(project), cover: form }, profile, title);
  const missing = missingCoverFields(profile);

  const save = async () => {
    setBusy(true);
    try {
      await updateCover(form);
      setMsg({ ok: true, text: "Opsi sampul tersimpan" });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal menyimpan" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">Sampul &amp; halaman depan</Pill>
        {missing.length > 0 ? <Pill tone="yellow">Profil belum lengkap</Pill> : <Pill tone="green">Profil lengkap</Pill>}
      </div>
      <div className="mt-4 grid gap-6 md:grid-cols-[1fr_260px]">
        <div>
          <p className="text-[13px] leading-relaxed text-graphite">
            Nama, NIM, program studi, fakultas, kampus, dan logo diambil dari profil Anda
            {missing.length > 0 ? ` (belum diisi: ${missing.join(", ")})` : ""}.{" "}
            <Link href="/profil" className="inline-flex items-center gap-1 font-medium text-brand underline underline-offset-2">
              <UserRound size={13} /> Ubah profil
            </Link>
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="docType">Jenis dokumen</Label>
              <Select id="docType" value={form.docType} onChange={(e) => set("docType", e.target.value as CoverOptions["docType"])}>
                <option value="SKRIPSI">Skripsi</option>
                <option value="PROPOSAL">Proposal skripsi</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="year">Tahun</Label>
              <Input
                id="year"
                type="number"
                inputMode="numeric"
                min={1990}
                max={2100}
                value={form.year ?? ""}
                placeholder={String(new Date().getFullYear())}
                onChange={(e) => set("year", e.target.value ? Number(e.target.value) : undefined)}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="degree">Gelar yang diperoleh</Label>
              <Input id="degree" value={form.degreeTitle} onChange={(e) => set("degreeTitle", e.target.value)} placeholder="Contoh: Sarjana Komputer (S.Kom.)" />
            </div>
            <div>
              <Label htmlFor="adv1">Dosen pembimbing I</Label>
              <Input id="adv1" value={form.advisor1} onChange={(e) => set("advisor1", e.target.value)} placeholder="Nama dan gelar" />
            </div>
            <div>
              <Label htmlFor="adv2">Dosen pembimbing II (opsional)</Label>
              <Input id="adv2" value={form.advisor2} onChange={(e) => set("advisor2", e.target.value)} placeholder="Nama dan gelar" />
            </div>
          </div>
          <fieldset className="mt-4">
            <legend className="mb-1.5 text-sm font-medium text-black/95">Halaman yang disertakan saat ekspor</legend>
            <div className="flex flex-wrap gap-x-5 gap-y-2 text-[13.5px]">
              {(
                [
                  ["titlePage", "Halaman judul dalam"],
                  ["approval", "Lembar persetujuan"],
                  ["originality", "Pernyataan keaslian"],
                ] as const
              ).map(([k, label]) => (
                <label key={k} className="inline-flex min-h-8 cursor-pointer items-center gap-2">
                  <input type="checkbox" checked={form[k]} onChange={(e) => set(k, e.target.checked)} />
                  {label}
                </label>
              ))}
            </div>
            <FieldHint>Sampul selalu ada. Pilih sesuai pedoman kampus Anda.</FieldHint>
          </fieldset>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={save} disabled={busy}>
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Simpan opsi sampul
            </Button>
            {msg && <span className={msg.ok ? "text-[13px] text-[#0a5f1e]" : "text-[13px] text-vermillion"}>{msg.text}</span>}
          </div>
        </div>
        <CoverPreview cover={model} className="mx-auto w-full max-w-[260px]" />
      </div>
    </Card>
  );
}
