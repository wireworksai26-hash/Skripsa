"use client";

import { CoverPreview } from "@/components/cover/cover-preview";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldHint, Input, Label } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { ThemeToggle } from "@/components/pwa/theme-toggle";
import { AccountCard } from "@/components/pwa/account-card";
import { ActivityCard } from "@/components/pwa/activity-card";
import { NotifyCard } from "@/components/pwa/notify-card";
import { coverInputOf, DEFAULT_COVER_OPTIONS, missingCoverFields, normalizeLogo, resolveCover } from "@/lib/cover";
import { useProfile, useProject } from "@/lib/store";
import type { Profile } from "@/lib/types";
import { Check, ImagePlus, Loader2, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const EMPTY: Profile = {
  fullName: "",
  nim: "",
  majorName: "",
  faculty: "",
  campusName: "",
  city: "",
  logoData: null,
  notifyPrefs: { draft: true, review: true, reminder: true },
};

export default function ProfilPage() {
  const stored = useProfile((s) => s.profile);
  const load = useProfile((s) => s.load);
  const save = useProfile((s) => s.save);
  const project = useProject((s) => s.project);

  const [form, setForm] = useState<Profile>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    load().catch((e) => setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal memuat profil" }));
  }, [load]);
  useEffect(() => {
    if (stored) setForm(stored);
  }, [stored]);

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => {
    setMsg(null);
    setForm((f) => ({ ...f, [k]: v }));
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    try {
      set("logoData", await normalizeLogo(file));
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Logo gagal diproses" });
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  const submit = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await save(form);
      setMsg({ ok: true, text: "Profil tersimpan. Data ini dipakai di sampul semua proyek Anda." });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal menyimpan" });
    } finally {
      setBusy(false);
    }
  };

  const title = project ? (project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? project.form.topic) : "Judul skripsi Anda akan tampil di sini";
  const input = project
    ? coverInputOf(project)
    : { language: "id", rules: undefined, cover: DEFAULT_COVER_OPTIONS };
  const model = resolveCover(input, form, title);
  const missing = missingCoverFields(form);
  const valid = form.fullName.trim() && form.majorName.trim() && form.campusName.trim();

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <Card>
        <Pill tone="blue">Data sampul</Pill>
        <h1 className="t-heading mt-3">Profil penulis</h1>
        <p className="mt-1 text-[13px] leading-relaxed text-graphite">
          Diisi sekali, dipakai di sampul, halaman judul, lembar persetujuan, dan pernyataan keaslian semua skripsi Anda. Isian yang kosong
          dicetak sebagai garis isian, tidak pernah diisi data karangan.
        </p>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="fullName">Nama lengkap</Label>
            <Input id="fullName" value={form.fullName} onChange={(e) => set("fullName", e.target.value)} autoComplete="name" />
          </div>
          <div>
            <Label htmlFor="nim">NIM</Label>
            <Input id="nim" value={form.nim} onChange={(e) => set("nim", e.target.value)} inputMode="numeric" placeholder="Contoh: 2101234567" />
          </div>
          <div>
            <Label htmlFor="major">Program studi / jurusan</Label>
            <Input id="major" value={form.majorName} onChange={(e) => set("majorName", e.target.value)} placeholder="Contoh: Teknik Informatika" />
          </div>
          <div>
            <Label htmlFor="faculty">Fakultas</Label>
            <Input id="faculty" value={form.faculty} onChange={(e) => set("faculty", e.target.value)} placeholder="Contoh: Fakultas Teknik" />
          </div>
          <div>
            <Label htmlFor="campus">Kampus</Label>
            <Input id="campus" value={form.campusName} onChange={(e) => set("campusName", e.target.value)} placeholder="Contoh: Universitas Contoh" />
          </div>
          <div>
            <Label htmlFor="city">Kota (untuk sampul dan tanda tangan)</Label>
            <Input id="city" value={form.city} onChange={(e) => set("city", e.target.value)} placeholder="Contoh: Bandung" />
          </div>
        </div>

        <div className="mt-6">
          <Label>Logo kampus</Label>
          <div className="flex flex-wrap items-center gap-4">
            <div className="grid h-24 w-24 place-items-center overflow-hidden rounded-card border border-dashed border-hairline-strong bg-white">
              {form.logoData ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={form.logoData} alt="Logo kampus" className="max-h-full max-w-full object-contain p-1" />
              ) : (
                <ImagePlus size={26} className="text-black/30" />
              )}
            </div>
            <div className="space-y-2">
              <input ref={fileRef} type="file" accept="image/*" className="sr-only" id="logo" onChange={(e) => onFile(e.target.files?.[0])} />
              <div className="flex flex-wrap gap-2">
                <Button variant="ghost" onClick={() => fileRef.current?.click()}>
                  <ImagePlus size={15} /> {form.logoData ? "Ganti logo" : "Unggah logo"}
                </Button>
                {form.logoData && (
                  <Button variant="danger" onClick={() => set("logoData", null)}>
                    <Trash2 size={15} /> Hapus
                  </Button>
                )}
              </div>
              <FieldHint>PNG, JPG, atau SVG. Otomatis dikecilkan ke PNG (maks 300 KB) agar ringan di berkas Word.</FieldHint>
            </div>
          </div>
        </div>

        {missing.length > 0 && (
          <p className="mt-5 text-[12.5px] text-black/55">Belum diisi: {missing.join(", ")}. Sampul tetap bisa diekspor dengan garis isian kosong.</p>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button size="lg" onClick={submit} disabled={busy || !valid}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
            {busy ? "Menyimpan…" : "Simpan profil"}
          </Button>
          {msg && <span className={msg.ok ? "text-[13px] text-[#0a5f1e]" : "text-[13px] text-vermillion"}>{msg.text}</span>}
        </div>
      </Card>

      <div className="space-y-6 lg:col-start-1">
        <Card>
          <h2 className="t-heading-sm">Tampilan</h2>
          <p className="mb-3 mt-1 text-[13px] text-graphite">Otomatis mengikuti pengaturan terang atau gelap perangkat Anda.</p>
          <ThemeToggle />
        </Card>
        <ActivityCard />
        <AccountCard />
        <NotifyCard prefs={form.notifyPrefs} onChange={(p) => set("notifyPrefs", p)} />
      </div>

      <div className="lg:sticky lg:top-24 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-start">
        <p className="mb-2 text-[12px] font-medium text-black/50">Pratinjau sampul</p>
        <CoverPreview cover={model} />
        {!project && <p className="mt-2 text-[11.5px] text-black/40">Judul, tahun, dan pembimbing diatur per proyek di Langkah 1.</p>}
      </div>
    </div>
  );
}
