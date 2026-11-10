import {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  ImageRun,
  NumberFormat,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  SimpleField,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
  type ParagraphChild,
} from "docx";
import { buildBibliography, renumberIeee } from "@/lib/citation";
import { BLANK, coverInputOf, imageSize, resolveCover } from "@/lib/cover";
import type { CampusTemplate } from "@/lib/templates";
import type { ChartSpec, Profile, ResultTable, ThesisProject } from "@/lib/types";
import { countWords } from "@/lib/utils";
import { chartToPng, dataUrlToBytes, type RasterImage } from "@/lib/visuals";

const TWIP_PER_CM = 566.929;
const PX_PER_CM = 96 / 2.54;
const MAX_FIGURE_HEIGHT_PX = 420;
const A4 = { width: 11906, height: 16838 }; // twip
const pt = (n: number) => n * 2; // docx memakai setengah-poin
const cm = (v: number) => Math.round(v * TWIP_PER_CM);

type Ps = CampusTemplate["page_setup"];
type Block = Paragraph | Table | TableOfContents;

interface ExportLabels {
  chapter: string;
  toc: string;
  listTables: string;
  listFigures: string;
  listCharts: string;
  chart: string;
  references: string;
  appendix: string;
  table: string;
  figure: string;
  note: string;
  draft: string;
  generatedLine: string;
  disclaimer: string;
  dateLocale: string;
  description: string;
  fallbackName: string;
}

const LABELS: Record<"id" | "en", ExportLabels> = {
  id: {
    chapter: "BAB",
    toc: "DAFTAR ISI",
    listTables: "DAFTAR TABEL",
    listFigures: "DAFTAR GAMBAR",
    listCharts: "DAFTAR GRAFIK",
    chart: "Grafik",
    references: "DAFTAR PUSTAKA",
    appendix: "LAMPIRAN",
    table: "Tabel",
    figure: "Gambar",
    note: "Catatan: ",
    draft: "DRAF SKRIPSI",
    generatedLine: "Draf dihasilkan dengan asistensi multi-agent Skripsa",
    disclaimer:
      "Dokumen ini adalah draf awal bahan bimbingan — wajib dievaluasi, ditulis ulang, dan disetujui bersama Dosen Pembimbing.",
    dateLocale: "id-ID",
    description: "Draf skripsi multi-agent",
    fallbackName: "draf-skripsi",
  },
  en: {
    chapter: "CHAPTER",
    toc: "TABLE OF CONTENTS",
    listTables: "LIST OF TABLES",
    listFigures: "LIST OF FIGURES",
    listCharts: "LIST OF CHARTS",
    chart: "Chart",
    references: "REFERENCES",
    appendix: "APPENDIX",
    table: "Table",
    figure: "Figure",
    note: "Note: ",
    draft: "THESIS DRAFT",
    generatedLine: "Draft produced with Skripsa multi-agent assistance",
    disclaimer:
      "This document is an initial draft for supervision — it must be evaluated, rewritten, and approved together with the academic supervisor.",
    dateLocale: "en-GB",
    description: "Multi-agent thesis draft",
    fallbackName: "thesis-draft",
  },
};

export interface BuildDeps {
  /** Dapat diganti (mis. saat uji) bila kanvas browser tidak tersedia. */
  renderChart?: (spec: ChartSpec) => Promise<RasterImage>;
}

export interface BuiltDocx {
  blob: Blob;
  figures: number;
  tables: number;
}

/** Nama berkas aman: tanpa tanda kutip/karakter terlarang, dipotong di batas kata (audit BUG-08). */
export function sanitize(name: string): string {
  const clean = name
    .replace(/[\u2018\u2019\u201C\u201D'"`]/g, "")
    .replace(/[\\/:*?<>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (clean.length <= 80) return clean.replace(/[.\s]+$/, "");
  const cut = clean.slice(0, 80);
  return cut.slice(0, cut.lastIndexOf(" ") > 40 ? cut.lastIndexOf(" ") : 80).replace(/[\s.,;:-]+$/, "");
}

/** Judul skripsi tidak diakhiri titik (audit BUG-08). */
export const cleanTitle = (t: string) => t.trim().replace(/[.\s]+$/, "");

export type HeadingNumbering = "decimal" | "alpha";

export interface ExportOptions {
  /** decimal = 1.1, 1.2; alpha = A., B. per bab (pedoman banyak FKIP/FBS). */
  numbering?: HeadingNumbering;
  /** Identitas penulis untuk sampul dan halaman depan; kosong = garis isian. */
  profile?: Profile | null;
  /** Sertakan bab yang belum ditulis sebagai judul kosong (kerangka). Bawaan: dilewati agar tidak ada halaman kosong. */
  includeEmpty?: boolean;
}

function roman(n: string): string {
  return ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"][Number(n) - 1] ?? n;
}

/** Pembuat paragraf dengan jenis dan ukuran huruf mengikuti templat kampus. */
function makeKit(ps: Ps) {
  const base = { font: ps.font_family, size: pt(ps.font_size_pt) };
  const run = (text: string, o: { bold?: boolean; italics?: boolean; size?: number; allCaps?: boolean } = {}) =>
    new TextRun({ text, font: ps.font_family, size: o.size ?? base.size, bold: o.bold, italics: o.italics, allCaps: o.allCaps });

  const body = (text: string) =>
    new Paragraph({
      alignment: AlignmentType.JUSTIFIED,
      indent: { firstLine: cm(ps.paragraph_indent_cm) },
      spacing: { line: Math.round(240 * ps.line_spacing), after: 0 },
      widowControl: true,
      children: [run(text)],
    });

  const centered = (text: string, o: { bold?: boolean; italics?: boolean; before?: number; after?: number; size?: number } = {}) =>
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: o.before ?? 0, after: o.after ?? 0, line: 240 },
      children: [run(text, { bold: o.bold, italics: o.italics, size: o.size })],
    });

  return { base, run, body, centered };
}

function chapterHeading(kit: ReturnType<typeof makeKit>, label: string, title: string, pageBreak = true): Paragraph {
  const { run } = kit;
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    alignment: AlignmentType.CENTER,
    pageBreakBefore: pageBreak,
    keepNext: true,
    spacing: { after: 360, line: 240 },
    children: label
      ? [run(label, { bold: true }), new TextRun({ break: 1 }), run(title, { bold: true })]
      : [run(title, { bold: true })],
  });
}

const LIST_ITEM = /^(\d{1,2}[.)]|[a-z][.)]|[-*•])\s+/;

/** Teks dengan penanda isian [DATA: ...] disorot kuning agar mahasiswa tidak lupa menggantinya. */
function runsWithPlaceholders(kit: ReturnType<typeof makeKit>, text: string): TextRun[] {
  return text
    .split(/(\[DATA:[^\]]*\])/i)
    .filter(Boolean)
    .map((part) =>
      /^\[DATA:/i.test(part)
        ? new TextRun({ text: part, font: kit.base.font, size: kit.base.size, highlight: "yellow" })
        : kit.run(part)
    );
}

/** Paragraf isi; butir daftar bernomor (rumusan masalah, tujuan, saran) dipertahankan sebagai daftar. */
function bodyParagraphs(kit: ReturnType<typeof makeKit>, ps: Ps, content: string): Paragraph[] {
  return content
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => {
      const m = p.match(LIST_ITEM);
      if (!m) {
        return new Paragraph({
          alignment: AlignmentType.JUSTIFIED,
          indent: { firstLine: cm(ps.paragraph_indent_cm) },
          spacing: { line: Math.round(240 * ps.line_spacing), after: 0 },
          widowControl: true,
          children: runsWithPlaceholders(kit, p),
        });
      }
      const marker = /^[-*•]$/.test(m[1]) ? "•" : m[1];
      return new Paragraph({
        alignment: AlignmentType.JUSTIFIED,
        indent: { left: cm(ps.paragraph_indent_cm + 0.6), hanging: cm(0.6) },
        spacing: { line: Math.round(240 * ps.line_spacing), after: 0 },
        children: [kit.run(`${marker}\t`), ...runsWithPlaceholders(kit, p.slice(m[0].length))],
      });
    });
}

function caption(kit: ReturnType<typeof makeKit>, label: string, chapterPrefix: string, n: number, text: string, above: boolean): Paragraph {
  const size = pt(Math.max(10, kit.base.size / 2 - 1));
  const children: ParagraphChild[] = [
    kit.run(`${label} ${chapterPrefix}`, { size }),
    // Bidang SEQ dengan nilai tersimpan: tetap tampil benar di penampil yang tidak memperbarui bidang,
    // dan Word memakainya untuk Daftar Tabel/Gambar.
    new SimpleField(`SEQ ${label} \\* ARABIC`, String(n)),
    kit.run(` ${text}`, { size }),
  ];
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: above,
    spacing: { before: above ? 240 : 60, after: above ? 100 : 240, line: 240 },
    children,
  });
}

const THIN = { style: BorderStyle.SINGLE, size: 4, color: "000000" };

function resultTable(kit: ReturnType<typeof makeKit>, ps: Ps, t: ResultTable): Table {
  const size = pt(Math.max(9, ps.font_size_pt - 1));
  const cell = (text: string, col: number, header: boolean) =>
    new TableCell({
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 50, bottom: 50, left: 90, right: 90 },
      shading: header ? { type: ShadingType.CLEAR, fill: "EDEDED", color: "auto" } : undefined,
      children: [
        new Paragraph({
          alignment: col === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
          spacing: { line: 240 },
          children: text
            .split(/(\[DATA:[^\]]*\])/i)
            .filter(Boolean)
            .map((part) =>
              /^\[DATA:/i.test(part)
                ? new TextRun({ text: part, font: kit.base.font, size, bold: header, highlight: "yellow" })
                : kit.run(part, { bold: header, size })
            ),
        }),
      ],
    });
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: { top: THIN, bottom: THIN, left: THIN, right: THIN, insideHorizontal: THIN, insideVertical: THIN },
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: t.columns.map((c, i) => cell(c, i, true)) }),
      ...t.rows.map((r) => new TableRow({ cantSplit: true, children: t.columns.map((_, i) => cell(r[i] ?? "", i, false)) })),
    ],
  });
}

interface FigureItem {
  caption: string;
  image: RasterImage;
  chapter: string;
  kind: "chart" | "diagram";
}

async function collectFigures(project: ThesisProject, deps: BuildDeps): Promise<FigureItem[]> {
  const render = deps.renderChart ?? chartToPng;
  const items: FigureItem[] = [];
  for (const c of project.charts) items.push({ caption: c.caption || c.title, image: await render(c), chapter: c.chapter ?? "4", kind: "chart" });
  for (const d of project.diagrams) {
    if (!d.image) continue;
    items.push({ caption: d.caption || d.title, image: { dataUrl: d.image, width: d.width ?? 800, height: d.height ?? 500 }, chapter: d.chapter ?? "4", kind: "diagram" });
  }
  return items;
}

function figureBlocks(kit: ReturnType<typeof makeKit>, ps: Ps, items: FigureItem[], prefix: string, label: string): Block[] {
  const textWidthPx = (21 - ps.margins_cm.left - ps.margins_cm.right) * PX_PER_CM;
  const out: Block[] = [];
  items.forEach(({ caption: text, image }, i) => {
    const ratio = Math.min(textWidthPx / image.width, MAX_FIGURE_HEIGHT_PX / image.height, 1.5);
    out.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        keepNext: true,
        spacing: { before: 240, after: 60 },
        children: [
          new ImageRun({
            type: "png",
            data: dataUrlToBytes(image.dataUrl),
            transformation: { width: Math.round(image.width * ratio), height: Math.round(image.height * ratio) },
            altText: { title: text, description: text, name: `${prefix}${i + 1}` },
          }),
        ],
      }),
      caption(kit, label, prefix, i + 1, text, false)
    );
  });
  return out;
}

function tableBlocks(kit: ReturnType<typeof makeKit>, ps: Ps, tables: ResultTable[], prefix: string, labels: ExportLabels): Block[] {
  const out: Block[] = [];
  tables.forEach((t, i) => {
    out.push(caption(kit, labels.table, prefix, i + 1, t.caption || t.title, true), resultTable(kit, ps, t));
    if (t.note) {
      out.push(
        new Paragraph({
          alignment: AlignmentType.JUSTIFIED,
          spacing: { before: 80, after: 240, line: 240 },
          children: [
            kit.run(labels.note, { italics: true, size: pt(Math.max(9, ps.font_size_pt - 2)) }),
            kit.run(t.note, { size: pt(Math.max(9, ps.font_size_pt - 2)) }),
          ],
        })
      );
    } else {
      out.push(new Paragraph({ spacing: { after: 200 }, children: [] }));
    }
  });
  return out;
}

export async function buildDocx(project: ThesisProject, deps: BuildDeps = {}, opts: ExportOptions = {}): Promise<BuiltDocx> {
  const template: CampusTemplate = project.template;
  const labels = LABELS[project.form.language === "en" ? "en" : "id"];
  const ps = template.page_setup;
  const kit = makeKit(ps);
  const { run, centered } = kit;
  const title = cleanTitle(project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? project.form.topic);

  const sections = template.citation_style === "IEEE" ? renumberIeee(project.sections) : project.sections;
  const figures = await collectFigures(project, deps);
  const tables = project.tables;

  const margins = { top: cm(ps.margins_cm.top), left: cm(ps.margins_cm.left), bottom: cm(ps.margins_cm.bottom), right: cm(ps.margins_cm.right) };
  const pageBase = { size: A4, margin: margins };

  /* ---------- isi: bab, subbab, visual ---------- */
  const chapterCodes = Array.from(new Set(sections.map((s) => s.chapterCode)));
  const tocEntries: Array<{ title: string; level: number }> = [];
  const bodyBlocks: Block[] = [];

  const hasContent = (ch: string) =>
    sections.some((s) => s.chapterCode === ch && countWords(s.content) > 0) || tables.some((t) => (t.chapter ?? "4") === ch) || figures.some((f) => f.chapter === ch);
  const skipped = opts.includeEmpty ? [] : chapterCodes.filter((ch) => !hasContent(ch));

  for (const ch of chapterCodes) {
    if (skipped.includes(ch)) continue;
    const chTitle = template.chapters.find((c) => c.chapter_number === ch)?.chapter_title ?? "";
    tocEntries.push({ title: `${labels.chapter} ${roman(ch)} ${chTitle}`, level: 1 });
    bodyBlocks.push(chapterHeading(kit, `${labels.chapter} ${roman(ch)}`, chTitle));

    const written = sections.filter((s) => s.chapterCode === ch && countWords(s.content) > 0);
    for (const [idx, sec] of written.entries()) {
      // Penomoran subbab: 1.1 (desimal) atau A., B. (pedoman yang memakai huruf kapital) — audit BUG-06.
      const depth = sec.sectionCode.split(".").length;
      const label = opts.numbering === "alpha" && depth <= 2 ? `${String.fromCharCode(65 + idx)}.` : sec.sectionCode;
      tocEntries.push({ title: `${label} ${sec.title}`, level: depth >= 3 ? 3 : 2 });
      bodyBlocks.push(
        new Paragraph({
          heading: depth >= 3 ? HeadingLevel.HEADING_3 : HeadingLevel.HEADING_2,
          keepNext: true,
          indent: depth >= 3 ? { left: cm(0.75) } : undefined,
          spacing: { before: depth >= 3 ? 240 : 360, after: 160, line: 240 },
          children: [run(`${label} ${sec.title}`, { bold: true, italics: depth >= 3 })],
        }),
        ...bodyParagraphs(kit, ps, sec.content)
      );
    }
    // Tabel & gambar ditempatkan di bab tujuannya dan bernomor per bab (Gambar 2.1, Tabel 3.1) — audit BUG-04.
    const tablesHere = tables.filter((t) => (t.chapter ?? "4") === ch);
    const figuresHere = figures.filter((f) => f.chapter === ch);
    bodyBlocks.push(...tableBlocks(kit, ps, tablesHere, `${ch}.`, labels), ...figureBlocks(kit, ps, figuresHere.filter((f) => f.kind === "chart"), `${ch}.`, labels.chart), ...figureBlocks(kit, ps, figuresHere.filter((f) => f.kind === "diagram"), `${ch}.`, labels.figure));
  }
  // Visual untuk bab yang tidak ada di templat: tetap disertakan sebagai lampiran, bukan dibuang diam-diam.
  const orphanTables = tables.filter((t) => !chapterCodes.includes(t.chapter ?? "4"));
  const orphanFigures = figures.filter((f) => !chapterCodes.includes(f.chapter));
  if (orphanTables.length > 0 || orphanFigures.length > 0) {
    tocEntries.push({ title: labels.appendix, level: 1 });
    bodyBlocks.push(
      chapterHeading(kit, "", labels.appendix),
      ...tableBlocks(kit, ps, orphanTables, "", labels),
      ...figureBlocks(kit, ps, orphanFigures.filter((f) => f.kind === "chart"), "", labels.chart),
      ...figureBlocks(kit, ps, orphanFigures.filter((f) => f.kind === "diagram"), "", labels.figure)
    );
  }

  /* ---------- daftar pustaka ---------- */
  const refs = project.references.filter((r) => project.selectedRefIds.includes(r.id));
  const entries = buildBibliography(refs, template.citation_style, sections);
  if (entries.length > 0) {
    tocEntries.push({ title: labels.references, level: 1 });
    bodyBlocks.push(chapterHeading(kit, "", labels.references));
    for (const e of entries) {
      bodyBlocks.push(
        new Paragraph({
          alignment: AlignmentType.JUSTIFIED,
          indent: { left: cm(1), hanging: cm(1) },
          spacing: { line: Math.round(240 * ps.line_spacing), after: 120 },
          widowControl: true,
          children: [
            ...(e.label ? [run(`${e.label} `)] : []),
            ...e.runs.map((r) => run(r.text, { italics: r.italic })),
          ],
        })
      );
    }
  }

  /* ---------- lampiran instrumen (kuesioner, pedoman wawancara) ---------- */
  project.appendices.forEach((a, i) => {
    const heading = `${labels.appendix} ${i + 1}`;
    tocEntries.push({ title: `${heading}. ${a.title}`, level: 1 });
    bodyBlocks.push(chapterHeading(kit, "", `${heading}. ${a.title}`));
    if (a.intro) bodyBlocks.push(kit.body(a.intro));
    a.items
      .filter((x) => x.trim())
      .forEach((item, k) =>
        bodyBlocks.push(
          new Paragraph({
            alignment: AlignmentType.JUSTIFIED,
            indent: { left: cm(1), hanging: cm(1) },
            spacing: { line: Math.round(240 * ps.line_spacing), after: 60 },
            children: [run(`${k + 1}.\t${item}`)],
            tabStops: [{ type: "left" as never, position: cm(1) }],
          })
        )
      );
  });

  /* ---------- sampul & halaman depan (mengikuti profil + aturan templat) ---------- */
  const cv = resolveCover(coverInputOf(project), opts.profile ?? null, title);
  const L = cv.labels;
  const bodySize = pt(cv.bodyPt);
  const titleSize = pt(cv.titlePt);

  const logoBlock = async (): Promise<Paragraph[]> => {
    if (!cv.logo) return [];
    try {
      const size = await imageSize(cv.logo);
      const width = Math.round(cv.logoCm * PX_PER_CM);
      const height = Math.round((width * size.height) / size.width);
      return [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 480, after: 480 },
          children: [
            new ImageRun({
              type: "png",
              data: dataUrlToBytes(cv.logo),
              transformation: { width, height },
              altText: { title: "Logo", description: "Logo kampus", name: "logo-kampus" },
            }),
          ],
        }),
      ];
    } catch {
      return [];
    }
  };

  const identity = (): Block[] => [
    centered(L.by, { before: 240, after: 60, size: bodySize }),
    centered(cv.name || BLANK, { bold: true, size: bodySize }),
    centered(`${L.nim} ${cv.nim || BLANK}`, { after: 480, size: bodySize }),
  ];
  const institution = (): Block[] => [
    centered(cv.program ? `${L.program} ${cv.program.toUpperCase()}` : `${L.program} ${BLANK}`, { bold: true, size: bodySize }),
    centered(cv.faculty ? `${L.faculty} ${cv.faculty.toUpperCase()}` : `${L.faculty} ${BLANK}`, { bold: true, size: bodySize }),
    centered(cv.campus ? cv.campus.toUpperCase() : BLANK, { bold: true, size: bodySize }),
    centered(cv.placeYear || String(new Date().getFullYear()), { bold: true, before: 120, size: bodySize }),
  ];
  const titleLines = (): Block[] => [
    centered(cv.docTypeLabel, { bold: true, before: 600, after: 360, size: titleSize }),
    centered(cv.title, { bold: true, after: 480, size: titleSize }),
    centered(cv.degreeLine, { after: 240, size: bodySize }),
  ];
  const pageTitle = (text: string, breakBefore: boolean) =>
    new Paragraph({ pageBreakBefore: breakBefore, alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [run(text, { bold: true, size: titleSize })] });
  const signature = (label: string, name: string): Block[] => [
    centered(label, { before: 480, size: bodySize }),
    new Paragraph({ spacing: { before: 1200 }, children: [] }),
    centered(name || BLANK, { bold: true, size: bodySize }),
  ];

  const cover: Block[] = [...titleLines(), ...(await logoBlock()), ...identity(), ...institution()];

  const frontPages: Block[] = [];
  const fm = project.front;
  const textPage = (heading: string, body: string[], extra: Block[] = []) => {
    frontPages.push(pageTitle(heading, frontPages.length > 0), ...body.map((p) => kit.body(p)), ...extra);
  };
  if (cv.titlePage) frontPages.push(...titleLines(), ...identity(), ...institution());
  if (cv.approval) {
    frontPages.push(
      pageTitle(L.approvalTitle, frontPages.length > 0),
      centered(cv.title, { bold: true, after: 240, size: bodySize }),
      centered(`${cv.name || BLANK} · ${L.nim} ${cv.nim || BLANK}`, { after: 240, size: bodySize }),
      centered(L.approvalIntro, { after: 240, size: bodySize }),
      ...signature(L.advisor1, cv.advisor1),
      ...(cv.advisor2 ? signature(L.advisor2, cv.advisor2) : [])
    );
  }
  const afterOriginality = () => {
    if (!fm) return;
    const kwLine = (label: string, kws: string[]): Block[] =>
      kws.length ? [new Paragraph({ spacing: { before: 200 }, children: [run(`${label}: `, { bold: true }), run(kws.join("; "), { italics: true })] })] : [];
    if (fm.abstractId) textPage("ABSTRAK", [fm.abstractId], kwLine("Kata kunci", fm.keywordsId));
    if (fm.abstractEn) textPage("ABSTRACT", [fm.abstractEn], kwLine("Keywords", fm.keywordsEn));
    if (fm.preface) textPage(project.form.language === "en" ? "PREFACE" : "KATA PENGANTAR", fm.preface.split(/\n\s*\n/).filter(Boolean));
  };
  if (cv.originality) {
    frontPages.push(
      pageTitle(L.originalityTitle, frontPages.length > 0),
      kit.body(L.originalityBody(cv.name, cv.nim, cv.program, cleanTitle(title))),
      new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 480 }, children: [run(`${cv.placeYear.split(" ").slice(0, -1).join(" ") || BLANK}, ${BLANK}`, { size: bodySize })] }),
      new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 120 }, children: [run(L.signed, { size: bodySize })] }),
      new Paragraph({ spacing: { before: 1200 }, children: [] }),
      new Paragraph({ alignment: AlignmentType.RIGHT, children: [run(cv.name || BLANK, { bold: true, size: bodySize })] }),
      new Paragraph({ alignment: AlignmentType.RIGHT, children: [run(`${L.nim} ${cv.nim || BLANK}`, { size: bodySize })] })
    );
  }
  afterOriginality();

  /* ---------- bagian awal: daftar isi, tabel, gambar ---------- */
  const front: Block[] = [
    ...frontPages,
    new Paragraph({ pageBreakBefore: frontPages.length > 0, alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [run(labels.toc, { bold: true })] }),
    new TableOfContents(labels.toc, { hyperlink: true, headingStyleRange: "1-3", cachedEntries: tocEntries }),
  ];
  if (skipped.length > 0) {
    const names = skipped.map((c) => roman(c)).join(", ");
    front.push(
      new Paragraph({
        spacing: { before: 360 },
        children: [
          run(project.form.language === "en" ? `Partial draft: chapter ${names} not written yet.` : `Draf parsial: bab ${names} belum ditulis.`, { italics: true, size: pt(Math.max(9, ps.font_size_pt - 2)) }),
        ],
      })
    );
  }
  if (tables.length > 0) {
    front.push(
      new Paragraph({ pageBreakBefore: true, alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [run(labels.listTables, { bold: true })] }),
      new TableOfContents(labels.listTables, { hyperlink: true, captionLabelIncludingNumbers: labels.table })
    );
  }
  if (figures.some((f) => f.kind === "diagram")) {
    front.push(
      new Paragraph({ pageBreakBefore: true, alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [run(labels.listFigures, { bold: true })] }),
      new TableOfContents(labels.listFigures, { hyperlink: true, captionLabelIncludingNumbers: labels.figure })
    );
  }
  if (figures.some((f) => f.kind === "chart")) {
    front.push(
      new Paragraph({ pageBreakBefore: true, alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [run(labels.listCharts, { bold: true })] }),
      new TableOfContents(labels.listCharts, { hyperlink: true, captionLabelIncludingNumbers: labels.chart })
    );
  }

  const footer = new Footer({
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: pt(10), font: ps.font_family })] })],
  });

  const heading = (size: number) => ({
    run: { font: ps.font_family, size: pt(size), bold: true, color: "000000" },
  });

  const doc = new Document({
    creator: "Skripsa",
    title,
    description: `${labels.description} — ${template.campus_name}. ${labels.generatedLine} · ${new Date().toLocaleDateString(labels.dateLocale)}. ${labels.disclaimer}`,
    features: { updateFields: true },
    styles: {
      default: { document: { run: { font: ps.font_family, size: pt(ps.font_size_pt) } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, ...heading(ps.font_size_pt) },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, ...heading(ps.font_size_pt) },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, ...heading(ps.font_size_pt) },
        { id: "TOC1", name: "toc 1", basedOn: "Normal", next: "Normal", run: { font: ps.font_family, size: pt(ps.font_size_pt) }, paragraph: { spacing: { before: 120, after: 40 } } },
        { id: "TOC2", name: "toc 2", basedOn: "Normal", next: "Normal", run: { font: ps.font_family, size: pt(ps.font_size_pt) }, paragraph: { indent: { left: 440 } } },
        { id: "TOC3", name: "toc 3", basedOn: "Normal", next: "Normal", run: { font: ps.font_family, size: pt(ps.font_size_pt) }, paragraph: { indent: { left: 880 } } },
      ],
    },
    sections: [
      { properties: { page: pageBase }, children: cover },
      { properties: { page: { ...pageBase, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } } }, footers: { default: footer }, children: front },
      { properties: { page: { ...pageBase, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } }, footers: { default: footer }, children: bodyBlocks },
    ],
  });

  return { blob: await Packer.toBlob(doc), figures: figures.length, tables: tables.length };
}

export async function exportDocx(project: ThesisProject, opts: ExportOptions = {}): Promise<string> {
  const { blob } = await buildDocx(project, {}, opts);
  const labels = LABELS[project.form.language === "en" ? "en" : "id"];
  const title = project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? project.form.topic;
  const name = `${sanitize(title) || labels.fallbackName}.docx`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return name;
}
