import type { Profile, SlidePlanItem, ThesisProject } from "@/lib/types";
import { chartToPng } from "@/lib/visuals";

const BRAND = "0075DE";
const INK = "1A1A1A";
const MUTED = "615D59";
const W = 13.333;
const H = 7.5;

const T = {
  id: { defense: "Sidang Skripsi", by: "Oleh", nim: "NIM", qa: "Pertanyaan yang Mungkin Muncul", thanks: "Terima kasih", questions: "Silakan bertanya", table: "Tabel", chart: "Grafik", figure: "Gambar", more: "baris lainnya, lihat naskah" },
  en: { defense: "Thesis Defense", by: "By", nim: "Student ID", qa: "Anticipated Questions", thanks: "Thank you", questions: "Questions are welcome", table: "Table", chart: "Chart", figure: "Figure", more: "more rows, see the thesis" },
};

/** Pertanyaan dari catatan Examiner: P1 · Fokus — "pertanyaan"\nSaran jawaban: ... */
function examinerQuestions(project: ThesisProject): string[] {
  const ex = project.reviews.find((r) => r.agent === "EXAMINER");
  if (!ex?.done) return [];
  return ex.notes.map((n) => /—\s*"([\s\S]+?)"\s*(?:\n|$)/.exec(n.text)?.[1]?.trim()).filter((q): q is string => !!q);
}

/** Susun .pptx dari rencana slide (ringkasan naskah), tabel, grafik, diagram, dan pertanyaan Examiner yang sudah ada. */
export async function buildPptx(project: ThesisProject, plan: SlidePlanItem[], profile: Profile | null): Promise<Blob> {
  const { default: PptxGenJS } = await import("pptxgenjs");
  const L = T[project.form.language === "en" ? "en" : "id"];
  const title = project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? project.form.topic;
  const font = "Calibri";
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.title = title;
  pptx.author = profile?.fullName ?? "Skripsa";

  let n = 0;
  const base = (heading: string) => {
    const s = pptx.addSlide();
    n += 1;
    s.background = { color: "FFFFFF" };
    s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.25, h: H, fill: { color: BRAND }, line: { color: BRAND } });
    s.addText(heading, { x: 0.7, y: 0.4, w: W - 1.4, h: 0.9, fontFace: font, fontSize: 30, bold: true, color: INK, valign: "middle" });
    s.addText(`${title.length > 80 ? title.slice(0, 77) + "…" : title}`, { x: 0.7, y: H - 0.55, w: W - 2.4, h: 0.35, fontFace: font, fontSize: 10, color: MUTED });
    s.addText(String(n), { x: W - 1.1, y: H - 0.55, w: 0.6, h: 0.35, fontFace: font, fontSize: 10, color: MUTED, align: "right" });
    return s;
  };

  // 1. judul
  const cover = pptx.addSlide();
  n += 1;
  cover.background = { color: "FFFFFF" };
  cover.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.5, h: H, fill: { color: BRAND }, line: { color: BRAND } });
  cover.addText(L.defense.toUpperCase(), { x: 1, y: 0.7, w: 9, h: 0.5, fontFace: font, fontSize: 16, bold: true, color: BRAND, charSpacing: 4 });
  cover.addText(title, { x: 1, y: 1.4, w: 10.3, h: 2.6, fontFace: font, fontSize: 34, bold: true, color: INK, valign: "top", fit: "shrink" });
  const who = [
    profile?.fullName ? `${L.by}: ${profile.fullName}${profile.nim ? ` · ${L.nim} ${profile.nim}` : ""}` : "",
    [profile?.majorName, profile?.faculty].filter(Boolean).join(" · "),
    profile?.campusName ?? "",
  ].filter(Boolean);
  if (who.length) cover.addText(who.join("\n"), { x: 1, y: 4.5, w: 9.5, h: 1.8, fontFace: font, fontSize: 18, color: MUTED, valign: "top" });
  if (profile?.logoData) cover.addImage({ data: profile.logoData, x: W - 3.2, y: 0.6, w: 1.9, h: 1.9, sizing: { type: "contain", w: 1.9, h: 1.9 } });

  // 2. ringkasan naskah per bagian
  for (const p of plan) {
    const s = base(p.title);
    s.addText(
      p.bullets.map((b) => ({ text: b, options: { bullet: { indent: 22 }, breakLine: true } })),
      { x: 0.8, y: 1.6, w: W - 1.6, h: H - 2.7, fontFace: font, fontSize: p.bullets.length > 4 ? 22 : 26, color: INK, valign: "top", paraSpaceAfter: 14 }
    );
    if (p.notes) s.addNotes(p.notes);
  }

  // 3. tabel hasil
  project.tables.slice(0, 6).forEach((t, i) => {
    const s = base(`${L.table} ${i + 1}. ${t.title}`.slice(0, 90));
    const rows = t.rows.slice(0, 9);
    const head = t.columns.map((c) => ({ text: c, options: { bold: true, color: "FFFFFF", fill: { color: BRAND }, fontFace: font, fontSize: 14 } }));
    const body = rows.map((r) => t.columns.map((_, ci) => ({ text: r[ci] ?? "", options: { fontFace: font, fontSize: 13, color: INK } })));
    s.addTable([head, ...body], { x: 0.8, y: 1.6, w: W - 1.6, border: { type: "solid", color: "D0D0D0", pt: 0.75 }, autoPage: false, valign: "middle" });
    if (t.rows.length > rows.length) s.addText(`+ ${t.rows.length - rows.length} ${L.more}`, { x: 0.8, y: H - 1.1, w: 8, h: 0.4, fontFace: font, fontSize: 12, color: MUTED });
  });

  // 4. grafik dan diagram (gambar)
  const pics: Array<{ label: string; caption: string; dataUrl: string; w: number; h: number }> = [];
  for (const c of project.charts.slice(0, 4)) {
    try {
      const img = await chartToPng(c);
      pics.push({ label: L.chart, caption: c.caption || c.title, dataUrl: img.dataUrl, w: img.width, h: img.height });
    } catch {
      /* grafik gagal dirender: lewati, jangan menggagalkan seluruh unduhan */
    }
  }
  for (const d of project.diagrams.filter((x) => x.image).slice(0, 4)) pics.push({ label: L.figure, caption: d.caption || d.title, dataUrl: d.image as string, w: d.width ?? 800, h: d.height ?? 500 });
  pics.forEach((pic, i) => {
    const s = base(`${pic.label} ${i + 1}. ${pic.caption}`.slice(0, 90));
    const maxW = W - 1.6;
    const maxH = H - 2.5;
    const ratio = Math.min(maxW / pic.w, maxH / pic.h);
    const w = pic.w * ratio;
    const h = pic.h * ratio;
    s.addImage({ data: pic.dataUrl, x: (W - w) / 2, y: 1.5 + (maxH - h) / 2, w, h });
  });

  // 5. pertanyaan Examiner
  const qs = examinerQuestions(project).slice(0, 6);
  if (qs.length) {
    const s = base(L.qa);
    s.addText(
      qs.map((q) => ({ text: q, options: { bullet: { type: "number" as const }, breakLine: true } })),
      { x: 0.8, y: 1.6, w: W - 1.6, h: H - 2.7, fontFace: font, fontSize: 18, color: INK, valign: "top", paraSpaceAfter: 10, fit: "shrink" }
    );
  }

  // 6. penutup
  const end = pptx.addSlide();
  n += 1;
  end.background = { color: BRAND };
  end.addText(L.thanks, { x: 0, y: 2.6, w: W, h: 1.2, fontFace: font, fontSize: 48, bold: true, color: "FFFFFF", align: "center" });
  end.addText(L.questions, { x: 0, y: 3.9, w: W, h: 0.7, fontFace: font, fontSize: 22, color: "FFFFFF", align: "center" });

  return (await pptx.write({ outputType: "blob" })) as Blob;
}
