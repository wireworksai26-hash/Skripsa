/**
 * Pencocokan kalimat rujukan ke teks PDF untuk stabilo kuning.
 *
 * Teks PDF datang sebagai potongan baris (item) dengan spasi, tanda hubung, dan pemenggalan yang berbeda
 * dari abstrak di basis data. Jadi kedua sisi dinormalisasi (huruf/angka saja), lalu dicari untai kata
 * berurutan ("shingle") yang muncul di halaman. Halaman dengan cakupan kata terbanyak dipilih.
 */

export interface TextItem {
  str: string;
}

export interface ItemSpan {
  item: number;
  /** Bagian item yang tersorot, sebagai pecahan 0..1 dari lebar item. */
  from: number;
  to: number;
}

export interface PageMatch {
  page: number; // 1-based
  /** Pecahan kata kalimat rujukan yang tercakup di halaman ini. */
  coverage: number;
  spans: ItemSpan[];
}

const SHINGLE = 4;
export const MIN_COVERAGE = 0.3;

export function normalize(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

interface PageIndex {
  text: string;
  /** Rentang [start, end) tiap item pada `text`; item kosong bernilai null. */
  ranges: Array<[number, number] | null>;
}

function indexPage(items: TextItem[]): PageIndex {
  let text = "";
  const ranges: PageIndex["ranges"] = [];
  let glue = false; // item sebelumnya berakhir tanda hubung: sambung tanpa spasi
  for (const it of items) {
    const raw = it.str.trimEnd();
    const hyphenEnd = /[-­‐]$/.test(raw);
    const n = normalize(hyphenEnd ? raw.slice(0, -1) : raw);
    if (!n) {
      ranges.push(null);
      continue;
    }
    if (text && !glue) text += " ";
    const start = text.length;
    text += n;
    ranges.push([start, text.length]);
    glue = hyphenEnd;
  }
  return { text, ranges };
}

function wordAligned(text: string, pos: number, len: number): boolean {
  const before = pos === 0 || text[pos - 1] === " ";
  const after = pos + len === text.length || text[pos + len] === " ";
  return before && after;
}

function mergeRanges(ranges: Array<[number, number]>): Array<[number, number]> {
  const sorted = [...ranges].sort((a, b) => a[0] - b[0]);
  const out: Array<[number, number]> = [];
  for (const r of sorted) {
    const last = out[out.length - 1];
    if (last && r[0] <= last[1] + 1) last[1] = Math.max(last[1], r[1]);
    else out.push([r[0], r[1]]);
  }
  return out;
}

export function matchPage(items: TextItem[], snippet: string, page: number): PageMatch {
  const words = normalize(snippet).split(" ").filter(Boolean);
  const empty: PageMatch = { page, coverage: 0, spans: [] };
  if (words.length === 0) return empty;

  const { text, ranges } = indexPage(items);
  if (!text) return empty;

  const k = Math.min(SHINGLE, words.length);
  const hits: Array<[number, number]> = [];
  const covered = new Set<number>();
  for (let i = 0; i + k <= words.length; i++) {
    const phrase = words.slice(i, i + k).join(" ");
    let from = 0;
    for (;;) {
      const pos = text.indexOf(phrase, from);
      if (pos < 0) break;
      if (wordAligned(text, pos, phrase.length)) {
        hits.push([pos, pos + phrase.length]);
        for (let w = i; w < i + k; w++) covered.add(w);
      }
      from = pos + 1;
    }
  }
  if (hits.length === 0) return empty;

  const merged = mergeRanges(hits);
  const spans: ItemSpan[] = [];
  ranges.forEach((r, item) => {
    if (!r) return;
    let lo = Infinity;
    let hi = -Infinity;
    for (const [s, e] of merged) {
      const a = Math.max(s, r[0]);
      const b = Math.min(e, r[1]);
      if (a < b) {
        lo = Math.min(lo, a);
        hi = Math.max(hi, b);
      }
    }
    if (hi > lo) {
      const width = r[1] - r[0];
      spans.push({ item, from: (lo - r[0]) / width, to: (hi - r[0]) / width });
    }
  });
  return { page, coverage: covered.size / words.length, spans };
}

/** Pilih halaman dengan cakupan tertinggi; null bila tak ada yang cukup meyakinkan. */
export function bestMatch(pages: TextItem[][], snippet: string): PageMatch | null {
  let best: PageMatch | null = null;
  pages.forEach((items, i) => {
    const m = matchPage(items, snippet, i + 1);
    if (m.coverage > (best?.coverage ?? 0)) best = m;
  });
  return best && (best as PageMatch).coverage >= MIN_COVERAGE ? best : null;
}
