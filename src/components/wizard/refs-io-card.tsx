"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import { Download, FileUp, Library } from "lucide-react";
import { useRef, useState } from "react";

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Impor BibTeX/RIS dari Zotero, Mendeley, atau EndNote; ekspor rujukan terpilih kembali ke format yang sama. */
export function RefsIoCard() {
  const project = useProject((s) => s.project);
  const setPart = useProject((s) => s.setPart);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<"in" | "out" | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  if (!project) return null;

  const run = async (kind: "in" | "out", fn: () => Promise<void>) => {
    setBusy(kind);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal" });
    } finally {
      setBusy(null);
    }
  };

  const doImport = (raw: string) =>
    run("in", async () => {
      const r = await api.importRefs(project.id, raw);
      const fresh = await api.loadThesis(project.id);
      setPart({ references: fresh.references, selectedRefIds: fresh.selectedRefIds });
      setText("");
      const warn = [r.without_year ? `${r.without_year} tanpa tahun` : "", r.without_authors ? `${r.without_authors} tanpa penulis` : ""].filter(Boolean).join(", ");
      setMsg({ ok: true, text: `${r.added} referensi ditambahkan, ${r.skipped_duplicates} duplikat dilewati.${warn ? ` Periksa: ${warn}.` : ""} Centang yang ingin dipakai di daftar rujukan.` });
    });

  return (
    <Card>
      <Pill tone="blue">
        <Library size={12} /> Zotero · Mendeley · EndNote
      </Pill>
      <h2 className="t-heading-sm mt-3">Impor dan ekspor referensi</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">Ekspor pustaka Anda sebagai BibTeX (.bib) atau RIS (.ris), lalu unggah di sini. Referensi yang sudah ada (judul sama) dilewati.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <input
          ref={fileRef}
          type="file"
          accept=".bib,.ris,.txt,text/plain"
          className="sr-only"
          aria-label="Berkas BibTeX atau RIS"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (f) await doImport(await f.text());
            if (fileRef.current) fileRef.current.value = "";
          }}
        />
        <Button variant="ghost" loading={busy === "in"} disabled={busy !== null} onClick={() => fileRef.current?.click()}>
          {busy !== "in" && <FileUp size={15} />} Unggah .bib / .ris
        </Button>
        <Button variant="text" loading={busy === "out"} disabled={busy !== null} onClick={() => run("out", async () => download(await api.exportRefs(project.id, "bibtex", true), "rujukan.bib"))}>
          {busy !== "out" && <Download size={15} />} Ekspor BibTeX
        </Button>
        <Button variant="text" disabled={busy !== null} onClick={() => run("out", async () => download(await api.exportRefs(project.id, "ris", true), "rujukan.ris"))}>
          <Download size={15} /> Ekspor RIS
        </Button>
      </div>
      <details className="mt-3">
        <summary className="min-h-8 cursor-pointer text-[13px] font-medium text-brand">Atau tempel teks BibTeX/RIS</summary>
        <Textarea className="mt-2" rows={6} value={text} onChange={(e) => setText(e.target.value)} placeholder="@article{...}  atau  TY  - JOUR ..." />
        <Button className="mt-2" variant="ghost" loading={busy === "in"} disabled={busy !== null || text.trim().length < 10} onClick={() => doImport(text)}>
          Impor teks
        </Button>
      </details>
      {msg && <p className={msg.ok ? "mt-3 text-[13px] text-[#0a5f1e]" : "mt-3 text-[13px] text-vermillion"}>{msg.text}</p>}
    </Card>
  );
}
