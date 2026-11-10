"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { AiStyleReport, WebCheckReport } from "@/lib/types";
import { Bot, Globe, ShieldCheck } from "lucide-react";
import { useState } from "react";

const tone = (label: string | null) => (label === "Tinggi" ? "coral" : label === "Sedang" ? "yellow" : label === "Rendah" ? "green" : "basic");

/** Pemeriksaan akhir (paling akhir di Review): kemiripan dengan literatur terbuka dan indikator gaya mirip AI. */
export function IntegrityCard() {
  const project = useProject((s) => s.project);
  const [busy, setBusy] = useState<"web" | "ai" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [web, setWeb] = useState<WebCheckReport | null>(null);
  const [ai, setAi] = useState<AiStyleReport | null>(null);
  if (!project) return null;

  const run = async (kind: "web" | "ai") => {
    setBusy(kind);
    setError(null);
    try {
      if (kind === "web") setWeb(await api.webCheck(project.id));
      else setAi(await api.aiStyle(project.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Pemeriksaan gagal");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="midnight">
          <ShieldCheck size={12} /> Pemeriksaan akhir
        </Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Plagiarisme dan gaya mirip AI</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Jalankan sebelum diserahkan ke pembimbing. Keduanya indikator untuk membantu Anda merapikan naskah, bukan putusan dan bukan pengganti alat resmi kampus.
      </p>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-card border border-hairline p-4">
          <p className="flex items-center gap-2 font-semibold">
            <Globe size={16} /> Kemiripan dengan literatur terbuka
          </p>
          <p className="mt-1 text-[12.5px] leading-relaxed text-black/55">Memeriksa hingga 24 frasa dari draf ke teks lengkap karya akses terbuka (OpenAlex). Tidak menjangkau karya berbayar maupun skripsi kampus, jadi hasil bersih belum berarti bebas plagiarisme.</p>
          <Button className="mt-3" onClick={() => run("web")} loading={busy === "web"} disabled={busy !== null}>
            {busy !== "web" && <Globe size={15} />} Periksa kemiripan
          </Button>
          {web && (
            <div className="mt-4 space-y-2 text-[13px]">
              <p className="text-black/60">
                {web.checked} frasa diperiksa{web.errors > 0 ? `, ${web.errors} gagal` : ""}; {web.matches.length} cocok.
              </p>
              {web.matches.length === 0 && web.checked > 0 && <p className="rounded-btn bg-[#f0faf0] p-2.5 text-[#0a4d1e]">Tidak ada frasa yang cocok dengan teks lengkap karya terbuka.</p>}
              {web.matches.map((m, i) => (
                <div key={i} className={`rounded-btn border p-2.5 ${m.in_your_references ? "border-hairline" : "border-vermillion/30 bg-vermillion/5"}`}>
                  <p className="text-[12px] text-black/50">
                    Subbab {m.section} · {m.section_title}
                    {m.own_writing ? " · tulisan Anda" : ""}
                  </p>
                  <p className="mt-1">“{m.phrase}”</p>
                  <p className="mt-1 text-black/65">
                    Cocok dengan: {m.source_title}
                    {m.source_year ? ` (${m.source_year})` : ""}
                    {m.other_hits > 0 ? ` dan ${m.other_hits}+ karya lain` : ""}
                    {m.source_doi ? (
                      <>
                        {" · "}
                        <a className="text-brand underline underline-offset-2" href={`https://doi.org/${m.source_doi}`} target="_blank" rel="noreferrer">
                          DOI
                        </a>
                      </>
                    ) : null}
                  </p>
                  <p className="mt-1 text-[12px] font-medium">{m.in_your_references ? "Ada di daftar rujukan Anda: pastikan dikutip dengan benar." : "Tidak ada di daftar rujukan: parafrasakan dan sitasi sumbernya."}</p>
                </div>
              ))}
              <p className="text-[11.5px] text-black/45">{web.note}</p>
            </div>
          )}
        </div>

        <div className="rounded-card border border-hairline p-4">
          <p className="flex items-center gap-2 font-semibold">
            <Bot size={16} /> Indikator gaya mirip AI
          </p>
          <p className="mt-1 text-[12.5px] leading-relaxed text-black/55">Menghitung pola teks: variasi panjang kalimat, frasa klise, pembuka berulang, keragaman kata. Tidak ada detektor AI yang andal; gunakan untuk menemukan bagian generik yang perlu ditulis ulang.</p>
          <Button className="mt-3" onClick={() => run("ai")} loading={busy === "ai"} disabled={busy !== null}>
            {busy !== "ai" && <Bot size={15} />} Periksa gaya tulisan
          </Button>
          {ai && (
            <div className="mt-4 space-y-2 text-[13px]">
              {ai.overall !== null ? (
                <p className="flex items-center gap-2">
                  <Pill tone={tone(ai.overall_label)}>
                    {ai.overall_label} · {ai.overall}
                  </Pill>
                  <span className="text-black/55">indikasi gaya generik pada subbab yang ditulis agen</span>
                </p>
              ) : (
                <p className="text-black/60">Belum ada subbab agen yang cukup panjang untuk dinilai.</p>
              )}
              <ul className="space-y-1.5">
                {ai.sections.map((s) => (
                  <li key={s.code} className="rounded-btn border border-hairline p-2.5">
                    <p className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">
                        {s.code} {s.title}
                      </span>
                      <Pill tone={tone(s.score === null ? null : s.label)}>{s.score === null ? s.label : `${s.label} · ${s.score}`}</Pill>
                      {s.imported && <Pill>tulisan Anda</Pill>}
                    </p>
                    {s.reasons.map((r) => (
                      <p key={r} className="mt-1 text-black/65">
                        • {r}
                      </p>
                    ))}
                    {s.examples.length > 0 && <p className="mt-1 text-[12px] text-black/50">Frasa klise: {s.examples.join(", ")}</p>}
                  </li>
                ))}
              </ul>
              <p className="rounded-btn bg-marigold/25 p-2.5 text-[12px] leading-relaxed text-black/75">{ai.disclaimer}</p>
            </div>
          )}
        </div>
      </div>
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}
    </Card>
  );
}
