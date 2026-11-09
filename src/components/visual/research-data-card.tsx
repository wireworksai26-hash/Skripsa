"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { askConfirm } from "@/components/ui/confirm";
import { FieldHint, Input, Label, Select, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { ResearchDataItem } from "@/lib/types";
import { Database, FileUp, Plus, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

const KIND_LABEL = { table: "Tabel angka (CSV)", text: "Teks: wawancara, observasi, dokumen" } as const;

/** Data penelitian milik pengguna untuk Bab IV. Angka diolah deterministik, teks dikodekan agen dengan kutipan terverifikasi. */
export function ResearchDataCard() {
  const project = useProject((s) => s.project);
  const reload = useProject((s) => s.reload);
  const [items, setItems] = useState<ResearchDataItem[]>([]);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"table" | "text">(project?.form.method === "KUALITATIF" ? "text" : "table");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const id = project?.id;

  const refresh = useCallback(async () => {
    if (id) setItems(await api.listData(id).catch(() => []));
  }, [id]);
  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!project) return null;
  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal" });
    } finally {
      setBusy(null);
    }
  };

  const add = () =>
    run("add", async () => {
      await api.addData(project.id, { title: title.trim(), kind, content });
      setTitle("");
      setContent("");
      await refresh();
      setMsg({ ok: true, text: "Data tersimpan. Tekan Olah dengan agen untuk menjadikannya tabel dan temuan Bab IV." });
    });

  const analyze = (d: ResearchDataItem) =>
    run(d.id, async () => {
      const r = await api.analyzeData(project.id, d.id);
      await Promise.all([refresh(), reload()]);
      setMsg({ ok: true, text: `Selesai (${r.provider}). Tabel hasil olah masuk ke Bab IV. Buat ulang subbab Bab IV di Langkah 4 agar penulis memakai data ini.` });
    });

  const remove = async (d: ResearchDataItem) => {
    if (!(await askConfirm(`Hapus data "${d.title}" beserta tabel hasil olahnya?`, { danger: true, confirmLabel: "Hapus" }))) return;
    await run(d.id, async () => {
      await api.deleteData(project.id, d.id);
      await Promise.all([refresh(), reload()]);
    });
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">
          <Database size={12} /> Data penelitian
        </Pill>
        <Pill>{items.length} kumpulan data</Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Masukkan data Anda untuk Bab IV</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Tempel atau unggah data hasil penelitian Anda. Agen hanya mengolah data ini: angka dihitung langsung (tanpa dikarang), dan tema dari teks wajib berkutip persis dari data Anda. Subbab Bab IV lalu ditulis dari hasil olah tersebut.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_260px]">
        <div>
          <Label htmlFor="dtitle">Nama data</Label>
          <Input id="dtitle" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Mis. Hasil kuesioner kelas XI atau Transkrip wawancara siswa" />
        </div>
        <div>
          <Label htmlFor="dkind">Jenis data</Label>
          <Select id="dkind" value={kind} onChange={(e) => setKind(e.target.value as "table" | "text")}>
            {Object.entries(KIND_LABEL).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </Select>
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor="dcontent">Isi data</Label>
          <Textarea
            id="dcontent"
            rows={7}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={kind === "table" ? "Baris pertama = judul kolom. Contoh:\nKelas;Skor;Motivasi\nA;80;4,5\nB;70;3,5" : "Tempel transkrip, catatan observasi, atau kutipan dokumen/buku teks yang Anda analisis."}
          />
          <FieldHint>{kind === "table" ? "Pemisah koma, titik koma, atau tab. Koma desimal Indonesia didukung." : "Minimal sekitar 40 kata. Makin lengkap datanya, makin kuat temanya."}</FieldHint>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.tsv,.txt,.md,text/plain,text/csv"
          className="sr-only"
          aria-label="Berkas data"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (f) {
              setContent(await f.text());
              if (!title.trim()) setTitle(f.name.replace(/\.[^.]+$/, ""));
            }
            if (fileRef.current) fileRef.current.value = "";
          }}
        />
        <Button variant="ghost" onClick={() => fileRef.current?.click()}>
          <FileUp size={15} /> Unggah berkas
        </Button>
        <Button onClick={add} loading={busy === "add"} disabled={busy !== null || !title.trim() || content.trim().length < 5}>
          {busy !== "add" && <Plus size={15} />} Simpan data
        </Button>
      </div>
      {msg && <p className={msg.ok ? "mt-3 text-[13px] text-[#0a5f1e]" : "mt-3 text-[13px] text-vermillion"}>{msg.text}</p>}

      {items.length > 0 && (
        <ul className="mt-5 space-y-3">
          {items.map((d) => (
            <li key={d.id} className="rounded-card border border-hairline p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="min-w-0 flex-1 truncate font-semibold">{d.title}</p>
                <Pill>{d.kind === "table" ? "Tabel" : "Teks"}</Pill>
                {d.analyzed ? <Pill tone="green">Sudah diolah</Pill> : <Pill tone="yellow">Belum diolah</Pill>}
              </div>
              <p className="mt-1 line-clamp-2 text-[12.5px] text-black/50">{d.content.replace(/\s+/g, " ").slice(0, 160)}</p>
              {d.analyzed && d.analysis.type === "table" && (
                <p className="mt-2 text-[13px] text-black/70">
                  {d.analysis.rows} baris diolah menjadi {d.analysis.tables?.length ?? 0} tabel (masuk Bab IV).
                </p>
              )}
              {d.analyzed && d.analysis.type === "text" && (
                <ul className="mt-2 space-y-1 text-[13px] text-black/70">
                  {d.analysis.themes?.map((t) => (
                    <li key={t.name}>
                      <strong>{t.name}</strong> · {t.excerpts.length} kutipan terverifikasi
                    </li>
                  ))}
                  {d.analysis.notes && <li className="text-black/50">Catatan agen: {d.analysis.notes}</li>}
                </ul>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => analyze(d)} loading={busy === d.id} disabled={busy !== null}>
                  {busy !== d.id && <Sparkles size={14} />} {d.analyzed ? "Olah ulang" : "Olah dengan agen"}
                </Button>
                <Button size="sm" variant="danger" onClick={() => remove(d)} disabled={busy !== null}>
                  <Trash2 size={14} /> Hapus
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
