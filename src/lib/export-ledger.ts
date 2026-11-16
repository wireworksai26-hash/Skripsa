import { AlignmentType, BorderStyle, Document, ExternalHyperlink, HeadingLevel, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType } from "docx";
import type { CitationLedger, LedgerEntry, LedgerUse } from "@/lib/types";

const FONT = "Calibri";

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const place = (u: LedgerUse) => (u.section === "-" ? "Naskah" : `Subbab ${u.section}${u.title ? ` ${u.title}` : ""}`);

/** Berkas CSV (UTF-8 dengan BOM agar terbuka benar di Excel): satu baris per kutipan. */
export function ledgerCsv(ledger: CitationLedger): string {
  const q = (v: string | number) => `"${String(v ?? "").replace(/"/g, '""').replace(/\r?\n/g, " ")}"`;
  const head = ["No", "Rujukan", "DOI/tautan", "Sumber data", "Bukti grounding (cuplikan abstrak)", "Subbab", "Penanda kutipan", "Kalimat yang mengutip", "Catatan"];
  const rows: string[] = [head.map(q).join(",")];
  for (const e of ledger.entries) {
    const link = e.doi_url || e.pdf_url;
    const base = [e.number, e.reference, link, e.source, e.evidence];
    if (e.uses.length === 0) rows.push([...base, "", "", "", "Tidak dikutip di naskah"].map(q).join(","));
    for (const u of e.uses) rows.push([...base, place(u), u.marker, u.sentence, u.year_mismatch ? "Tahun di naskah berbeda dengan rujukan" : ""].map(q).join(","));
  }
  for (const g of ledger.unverified ?? []) for (const u of g.uses) rows.push([ "", g.bibliography_entry, "", "Belum ter-grounding", "", place(u), u.marker, u.sentence, "Ada di daftar pustaka naskah, belum terverifikasi" ].map(q).join(","));
  for (const m of ledger.missing ?? []) for (const u of m.uses) rows.push(["", "", "", "", "", place(u), u.marker, u.sentence, "Tidak ada di daftar pustaka maupun grounding"].map(q).join(","));
  return String.fromCharCode(0xfeff) + rows.join("\r\n");
}

export function downloadLedgerCsv(ledger: CitationLedger, name: string): string {
  const file = `${name}.csv`;
  save(new Blob([ledgerCsv(ledger)], { type: "text/csv;charset=utf-8" }), file);
  return file;
}

const t = (text: string, o: { bold?: boolean; italics?: boolean; size?: number; color?: string } = {}) => new TextRun({ text, font: FONT, size: o.size ?? 21, bold: o.bold, italics: o.italics, color: o.color });
const para = (children: TextRun[] | (TextRun | ExternalHyperlink)[], after = 80, indent = 0) => new Paragraph({ children, spacing: { after }, indent: indent ? { left: indent } : undefined });
const cell = (text: string, w: number, bold = false, shade = false) =>
  new TableCell({
    width: { size: w, type: WidthType.PERCENTAGE },
    shading: shade ? { type: ShadingType.CLEAR, fill: "F1F1EF", color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({ children: [t(text, { bold, size: 19 })] })],
  });

function entryBlocks(e: LedgerEntry) {
  const out: Array<Paragraph> = [];
  out.push(new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 240, after: 60 }, keepNext: true, children: [t(`[${e.number}] ${e.short}`, { bold: true, size: 24 })] }));
  out.push(para([t(e.reference, { size: 21 })], 60));
  const src = [e.source && `Sumber data: ${e.source}`, e.page ? `halaman cuplikan: ${e.page}` : "", e.journal && `Jurnal: ${e.journal}`].filter(Boolean).join("  ·  ");
  if (src) out.push(para([t(src, { size: 18, color: "666666" })], 40));
  const link = e.doi_url || e.pdf_url;
  if (link) out.push(para([t("Tautan: ", { size: 18, color: "666666" }), new ExternalHyperlink({ link, children: [new TextRun({ text: link, font: FONT, size: 18, style: "Hyperlink" })] })], 60));
  out.push(para([t("Bukti grounding: ", { bold: true, size: 20 }), t(e.evidence ? `“${e.evidence}”` : "Tidak ada cuplikan tersimpan untuk rujukan ini.", { italics: !!e.evidence, size: 20 })], 80));
  if (e.uses.length === 0) out.push(para([t("Tidak dikutip di naskah.", { italics: true, size: 20, color: "9A5B00" })], 80));
  else {
    out.push(para([t(`Dikutip ${e.uses.length} kali:`, { bold: true, size: 20 })], 40));
    for (const u of e.uses) {
      out.push(new Paragraph({ spacing: { after: 40 }, indent: { left: 360 }, border: { left: { style: BorderStyle.SINGLE, size: 6, color: "C9C9C4", space: 6 } }, children: [t(`${place(u)}: `, { bold: true, size: 19 }), t(u.sentence, { size: 19 }), ...(u.year_mismatch ? [t("  (tahun di naskah berbeda dengan rujukan)", { italics: true, size: 18, color: "B00020" })] : [])] }));
      if (u.grounded_snippet && u.grounded_snippet !== e.evidence) out.push(new Paragraph({ spacing: { after: 40 }, indent: { left: 720 }, children: [t(`Bukti yang dipakai penulis agen: “${u.grounded_snippet}”`, { italics: true, size: 18, color: "555555" })] }));
    }
  }
  return out;
}

/** Buku bukti sitasi .docx: tabel ringkas, lalu bukti per rujukan dan tempat dikutip; untuk naskah unggahan juga yang tak terlacak. */
export async function downloadLedgerDocx(ledger: CitationLedger, title: string, name: string): Promise<string> {
  const children: Array<Paragraph | Table> = [];
  children.push(new Paragraph({ heading: HeadingLevel.TITLE, alignment: AlignmentType.LEFT, spacing: { after: 80 }, children: [t("Buku Bukti Sitasi", { bold: true, size: 40 })] }));
  children.push(para([t(title, { size: 24 })], 60));
  const dateStr = new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  const sourceLine = ledger.source === "upload" ? `Dilacak dari berkas ${ledger.filename ?? "naskah unggahan"}` : "Dihitung dari naskah di Skripsa";
  children.push(para([t(`${sourceLine}  ·  ${dateStr}`, { size: 19, color: "666666" })], 120));
  children.push(para([t(`${ledger.totals.references} rujukan ter-grounding, ${ledger.totals.cited} dikutip (${ledger.totals.uses} kutipan), ${ledger.totals.uncited} belum dikutip.`, { size: 21 })], 160));
  if (ledger.summary) {
    const s = ledger.summary;
    children.push(para([t(`Dari ${s.in_text} kutipan di naskah: ${s.tracked} terlacak ke grounding, ${s.year_mismatch} tahun berbeda, ${s.unverified} belum terverifikasi, ${s.missing} tidak ada di daftar pustaka.`, { size: 21, bold: true })], 160));
  }

  children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 }, children: [t("Ringkasan", { bold: true, size: 28 })] }));
  const widths = [6, 38, 8, 10, 38];
  children.push(
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      rows: [
        new TableRow({ tableHeader: true, children: ["No", "Rujukan", "Tahun", "Dikutip", "Subbab"].map((h, i) => cell(h, widths[i], true, true)) }),
        ...ledger.entries.map(
          (e) =>
            new TableRow({
              cantSplit: true,
              children: [String(e.number), e.short, String(e.year || ""), String(e.uses.length), Array.from(new Set(e.uses.map((u) => u.section))).join(", ") || "-"].map((v, i) => cell(v, widths[i])),
            })
        ),
      ],
    })
  );

  children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 320, after: 60 }, pageBreakBefore: true, children: [t("Bukti per rujukan", { bold: true, size: 28 })] }));
  for (const e of ledger.entries) children.push(...entryBlocks(e));

  const unv = ledger.unverified ?? [];
  const miss = ledger.missing ?? [];
  if (unv.length || miss.length) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 320, after: 60 }, pageBreakBefore: true, children: [t("Kutipan yang belum bisa dilacak", { bold: true, size: 28 })] }));
    for (const g of unv) {
      children.push(para([t("Belum terverifikasi: ", { bold: true, size: 21, color: "9A5B00" }), t(g.bibliography_entry, { size: 21 })], 40));
      for (const u of g.uses) children.push(new Paragraph({ spacing: { after: 30 }, indent: { left: 360 }, children: [t(`${place(u)}: `, { bold: true, size: 19 }), t(u.sentence, { size: 19 })] }));
    }
    for (const m of miss) {
      children.push(para([t(`Tidak ada di daftar pustaka: ${m.text}`, { bold: true, size: 21, color: "B00020" })], 40));
      for (const u of m.uses) children.push(new Paragraph({ spacing: { after: 30 }, indent: { left: 360 }, children: [t(`${place(u)}: `, { bold: true, size: 19 }), t(u.sentence, { size: 19 })] }));
    }
  }

  const doc = new Document({ creator: "Skripsa", title: "Buku Bukti Sitasi", sections: [{ properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } }, children }] });
  const file = `${name}.docx`;
  save(await Packer.toBlob(doc), file);
  return file;
}
