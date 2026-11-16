"use client";

import { LedgerList } from "@/components/review/ledger-list";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { CitationLedger, LedgerUse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BookMarked, Download, FileSearch, FileSpreadsheet, ShieldCheck, Upload } from "lucide-react";
import { useRef, useState } from "react";

type Mode = "platform" | "upload";

const fileSafe = (t: string) => t.replace(/[^\p{L}\p{N} _-]+/gu, " ").replace(/\s+/g, "-").replace(/^-+|-+$/g, "");
const where = (u: LedgerUse) => (u.section === "-" ? "Naskah" : `Subbab ${u.section}`);

function Group({ title, tone, children }: { title: string; tone: "bad" | "warn"; children: React.ReactNode }) {
  return (
    <div className={`rounded-btn border p-3 ${tone === "bad" ? "border-vermillion/30 bg-vermillion/5" : "border-saffron/40 bg-saffron/5"}`}>
      <p className="font-semibold">{title}</p>
      <div className="mt-1.5 space-y-2 text-[13px] text-black/75">{children}</div>
    </div>
  );
}

function Stat({ n, label, tone }: { n: number; label: string; tone?: "bad" | "warn" | "good" }) {
  return (
    <div className="rounded-btn border border-hairline p-3">
      <p className={cn("text-xl font-semibold tabular-nums", tone === "bad" && n > 0 && "text-vermillion", tone === "warn" && n > 0 && "text-[#9a5b00]", tone === "good" && "text-[#0a4d1e]")}>{n}</p>
      <p className="text-[12px] text-black/55">{label}</p>
    </div>
  );
}

/** Buku bukti sitasi (rujukan per kutipan) dan pelacak naskah jadi yang diunggah. Dihitung di server tanpa LLM. */
export function CitationLedgerCard() {
  const project = useProject((s) => s.project);
  const [mode, setMode] = useState<Mode>("platform");
  const [busy, setBusy] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [ledgers, setLedgers] = useState<Record<Mode, CitationLedger | null>>({ platform: null, upload: null });
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  if (!project) return null;

  const ledger = ledgers[mode];
  const title = project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? project.form.topic;
  const baseName = `Buku-Bukti-Sitasi-${fileSafe(title).slice(0, 50) || "skripsi"}${mode === "upload" ? "-naskah-jadi" : ""}`;
  const set = (m: Mode, v: CitationLedger) => setLedgers((l) => ({ ...l, [m]: v }));

  const loadPlatform = async () => {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      set("platform", await api.citationLedger(project.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal memuat buku bukti");
    } finally {
      setBusy(false);
    }
  };

  const track = async (f: File | null = file) => {
    if (!f) return;
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      set("upload", await api.trackUpload(project.id, f));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Naskah tidak dapat dilacak");
    } finally {
      setBusy(false);
    }
  };

  const verify = async (entries: string[]) => {
    setVerifying(true);
    setError(null);
    setNote(null);
    try {
      const r = await api.verifyLedgerEntries(project.id, entries.slice(0, 40));
      setNote(
        r.added + r.found.filter((f) => f.already).length > 0
          ? `${r.added} rujukan ditemukan di OpenAlex/Crossref dan ditambahkan ke grounding; ${r.not_found.length} tidak ditemukan (tidak ditambahkan).`
          : `Tidak ada yang ditemukan di OpenAlex/Crossref (${r.not_found.length} entri). Tidak ada yang ditambahkan; impor lewat BibTeX/RIS bila perlu.`
      );
      await track();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verifikasi gagal");
    } finally {
      setVerifying(false);
    }
  };

  const exportDocx = async () => {
    if (!ledger) return;
    try {
      const { downloadLedgerDocx } = await import("@/lib/export-ledger");
      setNote(`Tersimpan: ${await downloadLedgerDocx(ledger, title, baseName)}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ekspor gagal");
    }
  };

  const s = ledger?.summary;
  return (
    <Card>
      <Pill tone="blue">
        <BookMarked size={12} /> Grounding sitasi
      </Pill>
      <h2 className="t-heading-sm mt-3">Buku bukti sitasi</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Satu berkas rujukan untuk menjawab &ldquo;kutipan ini dari mana?&rdquo;: tiap rujukan beserta kalimat yang mengutipnya, subbabnya, tautan DOI, dan cuplikan abstrak sebagai buktinya. Dicocokkan langsung tanpa LLM, tidak ada rujukan yang dikarang.
      </p>

      <div className="mt-4 inline-flex rounded-btn bg-black/5 p-0.5 text-[13px] font-medium" role="tablist" aria-label="Sumber naskah">
        {(
          [
            ["platform", "Naskah di Skripsa"],
            ["upload", "Unggah naskah jadi"],
          ] as const
        ).map(([m, label]) => (
          <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)} className={cn("rounded-btn px-3.5 py-2.5 transition-colors sm:py-1.5", mode === m ? "bg-white shadow-sm" : "text-black/55")}>
            {label}
          </button>
        ))}
      </div>

      {mode === "platform" ? (
        <div className="mt-4">
          <Button onClick={loadPlatform} loading={busy}>
            {!busy && <BookMarked size={15} />} {ledgers.platform ? "Muat ulang" : "Buat buku bukti"}
          </Button>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <p className="text-[13px] text-black/65">
            Unggah naskah final (.docx atau .pdf) hasil sunting Anda. Setiap kutipannya dicocokkan ke rujukan yang sudah ter-grounding di proyek ini; yang tidak cocok ditandai. Berkas tidak disimpan.
          </p>
          <input
            ref={fileInput}
            type="file"
            accept=".docx,.pdf,.txt"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              if (f) void track(f);
              e.target.value = "";
            }}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => fileInput.current?.click()} loading={busy} variant={file ? "ghost" : "primary"}>
              {!busy && <Upload size={15} />} {file ? "Ganti berkas" : "Pilih berkas naskah"}
            </Button>
            {file && <span className="min-w-0 truncate text-[13px] text-black/60">{file.name}</span>}
            {file && (
              <Button variant="text" onClick={() => void track()} disabled={busy}>
                Periksa ulang
              </Button>
            )}
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}
      {note && <p className="mt-3 text-[13px] text-black/65">{note}</p>}

      {ledger && (
        <div className="mt-5 space-y-4 text-[13px]">
          {ledger.warnings?.map((w) => (
            <p key={w} className="rounded-btn bg-saffron/10 p-2.5 text-black/70">
              {w}
            </p>
          ))}
          {s ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <Stat n={s.in_text} label="kutipan di naskah" />
              <Stat n={s.tracked} label="terlacak ke grounding" tone="good" />
              <Stat n={s.year_mismatch} label="tahun berbeda" tone="bad" />
              <Stat n={s.unverified} label="belum terverifikasi" tone="warn" />
              <Stat n={s.missing} label="tak ada di daftar pustaka" tone="bad" />
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              <Stat n={ledger.totals.references} label="rujukan" />
              <Stat n={ledger.totals.uses} label="kutipan di naskah" tone="good" />
              <Stat n={ledger.totals.uncited} label="belum dikutip" tone="warn" />
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={exportDocx}>
              <Download size={14} /> Unduh buku bukti .docx
            </Button>
            <Button size="sm" variant="ghost" onClick={async () => {
                const { downloadLedgerCsv } = await import("@/lib/export-ledger");
                setNote(`Tersimpan: ${downloadLedgerCsv(ledger, baseName)}`);
              }}>
              <FileSpreadsheet size={14} /> Unduh .csv (Excel)
            </Button>
          </div>

          {(ledger.missing?.length ?? 0) > 0 && (
            <Group title={`${ledger.missing!.length} kutipan tidak ada di daftar pustaka maupun grounding`} tone="bad">
              {ledger.missing!.map((m, i) => (
                <div key={i}>
                  <p className="font-medium">{m.text}</p>
                  {m.uses.slice(0, 3).map((u, j) => (
                    <p key={j} className="text-black/60">
                      {where(u)}: {u.sentence}
                    </p>
                  ))}
                </div>
              ))}
              <p className="text-black/50">Periksa ejaan nama atau tahun, atau tambahkan rujukannya ke daftar pustaka.</p>
            </Group>
          )}

          {(ledger.unverified?.length ?? 0) > 0 && (
            <Group title={`${ledger.unverified!.length} rujukan ada di daftar pustaka naskah tetapi belum ter-grounding`} tone="warn">
              {ledger.unverified!.map((g, i) => (
                <div key={i}>
                  <p className="font-medium">{g.bibliography_entry}</p>
                  <p className="text-black/60">Dikutip {g.uses.length}× ({Array.from(new Set(g.uses.map(where))).join(", ")})</p>
                </div>
              ))}
              <Button size="sm" variant="ghost" loading={verifying} onClick={() => void verify(ledger.unverified!.map((g) => g.bibliography_entry))}>
                {!verifying && <ShieldCheck size={14} />} Cari di OpenAlex/Crossref &amp; tambahkan
              </Button>
              <p className="text-black/50">Hanya karya yang benar-benar ditemukan yang ditambahkan; buku sering tidak terdata.</p>
            </Group>
          )}

          {ledger.bibliography && !ledger.bibliography.found && <p className="rounded-btn bg-saffron/10 p-2.5 text-black/70">Judul &ldquo;DAFTAR PUSTAKA&rdquo; tidak ditemukan di berkas, jadi pencocokan daftar pustaka dilewati.</p>}
          {ledger.bibliography && ledger.bibliography.never_cited.length > 0 && (
            <Group title={`${ledger.bibliography.never_cited.length} entri daftar pustaka naskah tidak pernah dikutip di teks`} tone="warn">
              {ledger.bibliography.never_cited.slice(0, 15).map((r, i) => (
                <p key={i}>{r}</p>
              ))}
            </Group>
          )}

          <div>
            <p className="flex items-center gap-1.5 font-semibold">
              <FileSearch size={14} /> Rujukan ter-grounding
            </p>
            <LedgerList entries={ledger.entries} />
          </div>
        </div>
      )}
    </Card>
  );
}
