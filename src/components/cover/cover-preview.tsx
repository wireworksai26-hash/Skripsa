"use client";

import { BLANK, type CoverModel } from "@/lib/cover";
import { cn } from "@/lib/utils";

/** Pratinjau halaman A4 dengan susunan yang sama seperti sampul pada berkas DOCX. Ukuran huruf memakai satuan cqw agar ikut skala. */
export function CoverPreview({ cover, className }: { cover: CoverModel; className?: string }) {
  const L = cover.labels;
  const fs = (pt: number) => `${(pt * 100) / 595}cqw`; // lebar A4 = 595 pt
  const line = (v: string, extra?: string) =>
    v ? <p className={extra}>{v}</p> : <p className={cn("text-black/30", extra)}>{BLANK}</p>;

  return (
    <div className={cn("[container-type:inline-size]", className)}>
      <div
        className="paper relative mx-auto w-full overflow-hidden rounded-btn border border-hairline-strong bg-white text-center text-black shadow-sm"
        style={{ aspectRatio: "210 / 297", fontFamily: '"Times New Roman", Times, serif', fontSize: fs(cover.bodyPt), lineHeight: 1.35, padding: "9% 10%" }}
        aria-label="Pratinjau sampul"
      >
        <div className="flex h-full flex-col items-center justify-between">
          <div className="w-full">
            <p className="font-bold" style={{ fontSize: fs(cover.titlePt) }}>
              {cover.docTypeLabel}
            </p>
            <p className="mt-[4%] font-bold" style={{ fontSize: fs(cover.titlePt), lineHeight: 1.3 }}>
              {cover.title}
            </p>
            <p className="mt-[5%]">{cover.degreeLine}</p>
          </div>

          <div className="flex w-full flex-col items-center">
            {cover.logo ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={cover.logo} alt="Logo kampus" style={{ width: `${(cover.logoCm / 21) * 100}%`, maxHeight: "30cqw", objectFit: "contain" }} />
            ) : (
              <div
                className="grid place-items-center border border-dashed border-black/25 text-black/35"
                style={{ width: `${(cover.logoCm / 21) * 100}%`, aspectRatio: "1", fontSize: fs(9) }}
              >
                Logo
              </div>
            )}
          </div>

          <div className="w-full">
            <p>{L.by}</p>
            {line(cover.name, "font-bold")}
            <p>
              {L.nim} {cover.nim || BLANK}
            </p>
          </div>

          <div className="w-full font-bold">
            {line(cover.program ? `${L.program} ${cover.program.toUpperCase()}` : "")}
            {line(cover.faculty ? `${L.faculty} ${cover.faculty.toUpperCase()}` : "")}
            {line(cover.campus.toUpperCase())}
            <p className="mt-[1%]">{cover.placeYear}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
