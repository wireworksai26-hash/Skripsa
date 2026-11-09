import type { CitationStyle, InlineCitation, Reference, Section } from "@/lib/types";

/** Potongan teks dengan penanda cetak miring, agar judul jurnal bisa dimiringkan di UI maupun DOCX. */
export interface Run {
  text: string;
  italic?: boolean;
}

export interface BibEntry {
  /** Label di depan entri, mis. "[1]" pada IEEE. */
  label?: string;
  runs: Run[];
  ref: Reference;
}

const ANON = /^anonim$/i;

function surnameOf(author: string): string {
  if (author.includes(",")) return author.split(",")[0].trim();
  const parts = author.trim().split(/\s+/);
  return parts[parts.length - 1];
}

function givenOf(author: string): string {
  if (author.includes(",")) return author.split(",").slice(1).join(" ").trim();
  return author.trim().split(/\s+/).slice(0, -1).join(" ");
}

function initialsOf(author: string): string {
  return givenOf(author)
    .split(/[\s.]+/)
    .filter(Boolean)
    .map((g) => `${g[0].toUpperCase()}.`)
    .join(" ");
}

function realAuthors(ref: Reference): string[] {
  return ref.authors.filter((a) => a && !ANON.test(a.trim()));
}

/** Judul basis data sering KAPITAL SEMUA; ubah ke huruf kalimat agar layak masuk daftar pustaka. */
export function tidyTitle(title: string): string {
  const letters = title.replace(/[^A-Za-z]/g, "");
  const upper = letters.replace(/[^A-Z]/g, "").length;
  const clean = title.replace(/\s+/g, " ").trim().replace(/[.]+$/, "");
  if (letters.length < 8 || upper / letters.length < 0.7) return clean;
  const lower = clean.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function enDash(pages: string): string {
  return pages.replace(/(\d)\s*[-–—]\s*(\d)/g, "$1–$2");
}

function volIssue(ref: Reference): { vol?: string; issue?: string } {
  const v = ref.volumeIssue ?? "";
  return { vol: v.match(/^\s*([\w.]+)/)?.[1], issue: v.match(/\(([^)]+)\)/)?.[1] };
}

export function inTextMarker(style: CitationStyle, ref: Reference, index: number): string {
  const authors = realAuthors(ref);
  const last = surnameOf(authors[0] ?? "Anonim");
  const second = authors.length === 2 ? ` & ${surnameOf(authors[1])}` : "";
  const etal = authors.length > 2 ? " et al." : "";
  switch (style) {
    case "IEEE":
      return `[${index + 1}]`;
    case "CHICAGO":
    case "HARVARD":
      return `(${last}${second}${etal} ${ref.year})`;
    case "APA_7TH":
    default:
      return `(${last}${second}${etal}, ${ref.year})`;
  }
}

function apaAuthors(authors: string[]): string {
  const f = (a: string) => `${surnameOf(a)}, ${initialsOf(a)}`.replace(/,\s*$/, "");
  if (authors.length === 1) return f(authors[0]);
  if (authors.length <= 20) return `${authors.slice(0, -1).map(f).join(", ")}, & ${f(authors[authors.length - 1])}`;
  return `${authors.slice(0, 19).map(f).join(", ")}, … ${f(authors[authors.length - 1])}`;
}

function ieeeAuthors(authors: string[]): string {
  const f = (a: string) => `${initialsOf(a)} ${surnameOf(a)}`.trim();
  if (authors.length > 6) return `${f(authors[0])} et al.`;
  if (authors.length === 1) return f(authors[0]);
  if (authors.length === 2) return `${f(authors[0])} and ${f(authors[1])}`;
  return `${authors.slice(0, -1).map(f).join(", ")}, and ${f(authors[authors.length - 1])}`;
}

export function referenceRuns(ref: Reference, style: CitationStyle): Run[] {
  const authors = realAuthors(ref);
  const title = tidyTitle(ref.title);
  const { vol, issue } = volIssue(ref);
  const pages = ref.pages ? enDash(ref.pages) : "";
  const doiUrl = ref.doi ? `https://doi.org/${ref.doi}` : "";
  const runs: Run[] = [];

  if (style === "IEEE") {
    const head = `${authors.length ? `${ieeeAuthors(authors)}, ` : ""}"${title},"`;
    runs.push({ text: `${head} ` });
    if (ref.journal) runs.push({ text: ref.journal, italic: true });
    const tail = [
      vol ? `vol. ${vol}` : "",
      issue ? `no. ${issue}` : "",
      pages ? `pp. ${pages}` : "",
      String(ref.year),
      ref.doi ? `doi: ${ref.doi}` : "",
    ].filter(Boolean);
    runs.push({ text: `${ref.journal ? ", " : ""}${tail.join(", ")}.` });
    return runs;
  }

  if (style === "CHICAGO") {
    const who = authors.length ? `${authors.map((a, i) => (i === 0 ? `${surnameOf(a)}, ${givenOf(a)}` : `${givenOf(a)} ${surnameOf(a)}`)).join(", ")}. ` : "";
    runs.push({ text: `${who}"${title}." ` });
    if (ref.journal) runs.push({ text: ref.journal, italic: true });
    runs.push({ text: `${ref.journal ? " " : ""}${[vol, issue ? `no. ${issue}` : ""].filter(Boolean).join(", ")} (${ref.year})${pages ? `: ${pages}` : ""}.${doiUrl ? ` ${doiUrl}.` : ""}` });
    return runs;
  }

  if (style === "HARVARD") {
    const who = authors.length ? `${authors.map((a) => `${surnameOf(a)}, ${initialsOf(a)}`).join(", ")} ` : "";
    runs.push({ text: `${who}(${ref.year}) '${title}', ` });
    if (ref.journal) runs.push({ text: ref.journal, italic: true });
    runs.push({ text: `${[vol ? `, ${vol}` : "", issue ? `(${issue})` : "", pages ? `, pp. ${pages}` : ""].join("")}.${doiUrl ? ` Available at: ${doiUrl}.` : ""}` });
    return runs;
  }

  // APA 7th
  runs.push({ text: authors.length ? `${apaAuthors(authors)} (${ref.year}). ${title}. ` : `${title}. (${ref.year}). ` });
  if (ref.journal) {
    runs.push({ text: ref.journal, italic: true });
    if (vol) {
      runs.push({ text: ", " });
      runs.push({ text: vol, italic: true });
    }
    runs.push({ text: `${issue ? `(${issue})` : ""}${pages ? `, ${pages}` : ""}.${doiUrl ? ` ${doiUrl}` : ""}` });
  } else if (doiUrl) {
    runs.push({ text: doiUrl });
  }
  return runs;
}

export const runsToText = (runs: Run[]): string => runs.map((r) => r.text).join("");

export function referenceString(ref: Reference, style: CitationStyle): string {
  return runsToText(referenceRuns(ref, style));
}

/* ---------- urutan sitasi & penomoran IEEE ---------- */

function declared(sec: Section): InlineCitation[] {
  const text = sec.content;
  const pos = (c: InlineCitation) => {
    const i = c.marker ? text.indexOf(c.marker) : -1;
    return i < 0 ? Number.MAX_SAFE_INTEGER : i;
  };
  return [...sec.citations].sort((a, b) => pos(a) - pos(b));
}

/** ID rujukan menurut kemunculan pertama di naskah (bab dan subbab berurutan). */
export function citationOrder(sections: Section[]): string[] {
  const seen = new Set<string>();
  for (const sec of sections) for (const c of declared(sec)) seen.add(c.referenceId);
  return [...seen];
}

/**
 * IEEE menomori rujukan berurutan di seluruh dokumen, sedangkan penulis memberi nomor lokal per subbab.
 * Fungsi ini menulis ulang penanda di isi tiap subbab agar sesuai nomor global dan daftar pustaka.
 */
export function renumberIeee(sections: Section[]): Section[] {
  const order = citationOrder(sections);
  const num = new Map(order.map((id, i) => [id, i + 1]));
  return sections.map((sec) => {
    let content = sec.content;
    const seen = new Set<string>();
    declared(sec).forEach((c, i) => {
      if (!c.marker || seen.has(c.marker)) return;
      seen.add(c.marker);
      content = content.split(c.marker).join(`\u0000${i}\u0000`);
    });
    declared(sec).forEach((c, i) => {
      content = content.split(`\u0000${i}\u0000`).join(`[${num.get(c.referenceId)}]`);
    });
    return { ...sec, content };
  });
}

function sortKey(ref: Reference): string {
  const a = realAuthors(ref)[0];
  return `${a ? surnameOf(a) : tidyTitle(ref.title)}`.toLowerCase();
}

/**
 * Daftar pustaka: hanya rujukan yang dikutip di naskah (bila belum ada sitasi sama sekali, semua rujukan terpilih).
 * APA/Harvard/Chicago berurut abjad; IEEE berurut kemunculan, berlabel [n].
 */
export function buildBibliography(refs: Reference[], style: CitationStyle, sections: Section[]): BibEntry[] {
  const order = citationOrder(sections);
  const byId = new Map(refs.map((r) => [r.id, r]));
  const cited = order.map((id) => byId.get(id)).filter((r): r is Reference => !!r);
  const pool = cited.length > 0 ? cited : refs;

  if (style === "IEEE") {
    return pool.map((ref, i) => ({ label: `[${i + 1}]`, runs: referenceRuns(ref, style), ref }));
  }
  return [...pool]
    .sort((a, b) => sortKey(a).localeCompare(sortKey(b), "id") || a.year - b.year)
    .map((ref) => ({ runs: referenceRuns(ref, style), ref }));
}

export function bibliography(refs: Reference[], style: CitationStyle, sections: Section[] = []): string[] {
  return buildBibliography(refs, style, sections).map((e) => `${e.label ? `${e.label} ` : ""}${runsToText(e.runs)}`);
}
