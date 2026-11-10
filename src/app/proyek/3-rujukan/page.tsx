"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FoundationalCard } from "@/components/wizard/foundational-card";
import { RefsIoCard } from "@/components/wizard/refs-io-card";
import { Pill } from "@/components/ui/pill";
import { useProject } from "@/lib/store";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  CalendarClock,
  ChevronDown,
  Database,
  Loader2,
  MoveRight,
  Scroll,
  Search,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Reference } from "@/lib/types";

const GAP_HINTS = [
  "future research",
  "further research",
  "future studies",
  "belum",
  "gap",
  "not yet",
  "unexplored",
  "unknown",
  "remains",
  "limited",
  "saran",
];

function gapExtraction(refs: Reference[]): { id: string; title: string; sentence: string }[] {
  const out: { id: string; title: string; sentence: string }[] = [];
  for (const r of refs) {
    if (!r.abstract) continue;
    const sents = r.abstract.split(/(?<=[.!?])\s+/);
    const hit = sents.find((s) => GAP_HINTS.some((h) => s.toLowerCase().includes(h)));
    if (hit) out.push({ id: r.id, title: r.title, sentence: hit.trim() });
  }
  return out;
}

export default function RujukanPage() {
  const router = useRouter();
  const project = useProject((s) => s.project);
  const searchReferences = useProject((s) => s.searchReferences);
  const selectAllRefs = useProject((s) => s.selectAllRefs);
  const selectRecentRefs = useProject((s) => s.selectRecentRefs);
  const [recentOnly, setRecentOnly] = useState(false);
  const [recentMsg, setRecentMsg] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (!project) router.replace("/proyek/1-inisiasi");
  }, [project, router]);

  if (!project) return null;

  const run = async () => {
    setLoading(true);
    setFailure(null);
    try {
      setErrors(await searchReferences(recentOnly));
      setFetched(true);
    } catch (e) {
      setFailure(e instanceof Error ? e.message : "Pencarian rujukan gagal");
    } finally {
      setLoading(false);
    }
  };

  const select = (on: boolean) =>
    selectAllRefs(on).catch((e) => setFailure(e instanceof Error ? e.message : "Gagal menyimpan pilihan"));

  const selected = project.selectedRefIds;
  const thisYear = new Date().getFullYear();
  const recentCount = Math.min(15, project.references.filter((r) => r.year >= thisYear - 4).length);
  const gapList = gapExtraction(project.references.filter((r) => selected.includes(r.id)));

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="blue">
            <Database size={12} /> OpenAlex · Crossref · DOAJ · ERIC · CORE{project.form.domain === "INFORMATIKA" ? " · arXiv" : ""}
          </Pill>
          <Pill>{selected.length}/15 terpilih</Pill>
        </div>
        <h1 className="t-heading mt-4">Tarik & verifikasi rujukan ilmiah nyata</h1>
        <p className="t-serif-lede mt-2 text-graphite">
          Literature Agent menarik artikel jurnal dari basis data publik gratis. Abstrak tiap artikel
          bisa Anda buka, dan DOI aktif mudah diuji ulang oleh dosen pembimbing.
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button onClick={run} disabled={loading}>
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={15} />}
            {fetched ? "Tarik ulang" : "Tarik 10-15 artikel"}
          </Button>
          {project.references.length > 0 && (
            <>
              <Button variant="ghost" onClick={() => select(true)}>
                Pilih {Math.min(15, project.references.length)} teratas
              </Button>
              <Button
                variant="ghost"
                disabled={recentCount === 0}
                onClick={() =>
                  selectRecentRefs()
                    .then((n) => setRecentMsg(`${n} rujukan ${thisYear - 4}–${thisYear} dipilih.`))
                    .catch((e) => setFailure(e instanceof Error ? e.message : "Gagal menyimpan pilihan"))
                }
                title={recentCount === 0 ? `Tidak ada rujukan ${thisYear - 4}–${thisYear} di daftar ini` : undefined}
              >
                <CalendarClock size={14} /> Pilih 5 tahun terakhir ({recentCount})
              </Button>
              <Button variant="text" onClick={() => select(false)}>
                Bersihkan pilihan
              </Button>
            </>
          )}
          <label className="flex items-center gap-2 text-[13px] text-black/65">
            <input type="checkbox" checked={recentOnly} onChange={(e) => setRecentOnly(e.target.checked)} disabled={loading} />
            Hanya cari {thisYear - 4}–{thisYear}
          </label>
        </div>
        {recentMsg && <p className="mt-2 text-[12.5px] text-graphite">{recentMsg}</p>}
        {failure && (
          <p className="mt-3 flex items-center gap-1.5 text-[13px] text-vermillion">
            <AlertTriangle size={13} /> {failure}
          </p>
        )}
        {errors.length > 0 && fetched && (
          <p className="mt-3 flex items-center gap-1.5 text-[13px] text-vermillion">
            <AlertTriangle size={13} /> Sumber gagal dijangkau: {errors.join(", ")} — hasil dari sumber lain tetap tampil.
          </p>
        )}
      </Card>

      <FoundationalCard />

      <RefsIoCard />

      {project.references.length === 0 && (
        <Card className="border-dashed text-center text-[13px] text-black/55">
          {fetched
            ? "Tidak ada artikel ditemukan untuk kombinasi kata kunci ini. Coba tarik ulang atau perluas topik."
            : "Belum ada hasil. Tekan tombol Tarik 10-15 artikel di atas."}
        </Card>
      )}

      <div className="space-y-3">
        {project.references.map((r) => (
          <RefCard key={r.id} r={r} />
        ))}
      </div>

      {gapList.length > 0 && (
        <Card className="border-marigold/60 bg-marigold/[0.07]">
          <div className="flex items-center gap-2">
            <Scroll size={16} className="text-saffron" />
            <h2 className="t-heading-sm">Analisis celah penelitian (dari abstrak asli)</h2>
          </div>
          <ul className="mt-3 space-y-3">
            {gapList.map((g) => (
              <li key={g.id} className="rounded-btn bg-white p-4 text-[13px]">
                <p className="font-medium text-black/85 line-clamp-2">{g.title}</p>
                <p className="mt-1 text-graphite">“{g.sentence}”</p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {project.references.length > 0 && (
        <div className="flex justify-end">
          <Button size="lg" onClick={() => router.push("/proyek/4-draf")}>
            Lanjut: Daftar Draf Subbab <MoveRight size={15} />
          </Button>
        </div>
      )}
    </div>
  );
}

function RefCard({ r }: { r: Reference }) {
  const project = useProject((s) => s.project);
  const toggleRef = useProject((s) => s.toggleRef);
  const [failed, setFailed] = useState<string | null>(null);
  const picked = project?.selectedRefIds.includes(r.id) ?? false;
  const [open, setOpen] = useState(false);

  return (
    <div
      className={cn(
        "rounded-card border p-5 transition-colors duration-200",
        picked ? "border-brand bg-sky-tint" : "border-hairline bg-white"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="cursor-pointer font-semibold text-black/95">{r.title}</h3>
          <p className="mt-1 text-[13px] text-black/60">
            {r.authors.slice(0, 3).join(", ")}
            {r.authors.length > 3 ? " et al." : ""} · {r.year} · {r.journal ?? "—"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setFailed(null);
            toggleRef(r.id).catch((e) => setFailed(e instanceof Error ? e.message : "Gagal menyimpan pilihan"));
          }}
          aria-label={picked ? "Batal pilih" : "Pilih rujukan"}
          className={cn(
            "mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[13px] font-bold transition-colors",
            picked ? "border-brand bg-brand text-white" : "border-black/25 text-transparent hover:bg-black/5"
          )}
        >
          ✓
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {r.source.startsWith("Teori") && <Pill tone="blue">Teori dasar</Pill>}
        <Pill tone="basic">{r.source.replace(/^Teori · /, "")}</Pill>
        {typeof r.citedBy === "number" && r.citedBy > 0 && <Pill tone="sky">Sitasi {r.citedBy}</Pill>}
        {r.doi && (
          <a
            href={`https://doi.org/${r.doi}`}
            target="_blank"
            rel="noreferrer"
            className="text-[12px] font-medium text-brand underline decoration-brand/30 hover:decoration-brand"
          >
            DOI: {r.doi}
          </a>
        )}
        {r.oaUrl && r.oaUrl.startsWith("http") && (
          <a
            href={r.oaUrl}
            target="_blank"
            rel="noreferrer"
            className="text-[12px] font-medium text-brand underline decoration-brand/30 hover:decoration-brand"
          >
            Teks penuh ↓
          </a>
        )}
        {r.abstract && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1 text-[12px] font-medium text-black/55 hover:text-black/80"
          >
            {open ? "Sembunyikan abstrak" : "Lihat abstrak"}
            <ChevronDown size={13} className={cn("transition-transform", open && "rotate-180")} />
          </button>
        )}
      </div>
      {failed && <p className="mt-2 text-[12px] text-vermillion">{failed}</p>}
      {open && r.abstract && (
        <p className="mt-3 rounded-btn bg-black/[0.03] p-3 text-[13px] leading-relaxed text-graphite">
          {r.abstract}
        </p>
      )}
    </div>
  );
}
