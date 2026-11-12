/** Pembaca daftar isi/struktur bab dari teks tempelan (Word, PDF, pedoman). Murni deterministik, tanpa LLM. */

export interface ParsedRow {
  title: string;
  level: 1 | 2;
  /** Target kata bila tertulis, mis. "(400 kata)". */
  words?: number;
}
export interface ParsedChapter {
  title: string;
  rows: ParsedRow[];
}
export interface ParsedOutline {
  chapters: ParsedChapter[];
  warnings: string[];
}

export const MAX_CHAPTERS = 12;
export const MAX_ROWS_PER_CHAPTER = 30;

const ROMAN: Record<string, number> = { I: 1, V: 5, X: 10, L: 50, C: 100 };
const romanToInt = (s: string): number => {
  let total = 0;
  const up = s.toUpperCase();
  for (let i = 0; i < up.length; i++) {
    const v = ROMAN[up[i]] ?? 0;
    const next = ROMAN[up[i + 1]] ?? 0;
    total += v < next ? -v : v;
  }
  return total;
};

const CHAPTER_RE = /^(?:BAB|CHAPTER|BAGIAN)\s+([IVXLC]+|\d{1,2})\b[\s.:–—-]*(.*)$/i;
const NUMBERED_RE = /^(\d{1,2}(?:\.\d{1,2}){1,4})[.)]?\s+(\S.*)$/;
const SIMPLE_NUM_RE = /^(\d{1,2})[.)]\s+(\S.*)$/;
const LETTER_RE = /^[a-z][.)]\s+(\S.*)$/i;
const BULLET_RE = /^[-*•●▪]\s+/;
const WORDS_RE = /\s*[([]\s*(\d{2,4})\s*(?:kata|words?)\s*[)\]]\s*$/i;

/** Hapus titik-titik penuntun dan nomor halaman di ujung baris ("Background ........ 4"). */
function stripPageNumber(line: string): string {
  return line
    .replace(/\s*[.·…_\-–]{2,}\s*(?:\d{1,3}|[ivxlc]{1,6})\s*$/i, "")
    .replace(/\t+\s*(?:\d{1,3}|[ivxlc]{1,6})\s*$/i, "")
    .replace(/ {3,}\d{1,3}\s*$/, "");
}

const cleanTitle = (s: string) => s.replace(/\s+/g, " ").replace(/[:;.\s]+$/, "").trim();

const indentOf = (raw: string) => (raw.match(/^[ \t]*/)?.[0] ?? "").replace(/\t/g, "    ").length;

export function parseOutline(text: string, fallbackChapterTitles: string[] = []): ParsedOutline {
  const warnings: string[] = [];
  const chapters: ParsedChapter[] = [];
  let current: ParsedChapter | null = null;
  let currentNo = 0; // nomor bab yang sedang dibuka (dari judul bab atau awalan kode 2.1)
  let level1Indent = -1;
  let flattened = 0;
  let promoted = 0;
  let skippedRows = 0;

  const lines = text.replace(/\r/g, "").split("\n");

  const openChapter = (title: string, no: number) => {
    currentNo = no;
    current = { title: cleanTitle(title), rows: [] };
    chapters.push(current);
    level1Indent = -1;
  };
  const addRow = (title: string, level: 1 | 2, words?: number) => {
    if (!current || !title) return;
    if (current.rows.length >= MAX_ROWS_PER_CHAPTER) {
      skippedRows += 1;
      return;
    }
    if (level === 2 && !current.rows.some((r) => r.level === 1)) {
      level = 1; // sub-subbab tanpa induk dijadikan subbab
      promoted += 1;
    }
    current.rows.push({ title: title.slice(0, 140), level, ...(words ? { words } : {}) });
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    let line = stripPageNumber(raw.trim());
    if (!line) continue;
    line = line.replace(BULLET_RE, "").trim();
    if (!line) continue;

    let words: number | undefined;
    const wm = line.match(WORDS_RE);
    if (wm) {
      words = Math.max(50, Math.min(4000, Number(wm[1])));
      line = line.slice(0, wm.index).trim();
    }

    const ch = line.match(CHAPTER_RE);
    if (ch) {
      let title = ch[2];
      // "BAB I" di satu baris dan judulnya di baris berikutnya.
      if (!cleanTitle(title)) {
        for (let j = i + 1; j < lines.length; j++) {
          const nxt = stripPageNumber(lines[j].trim());
          if (!nxt) continue;
          if (!CHAPTER_RE.test(nxt) && !NUMBERED_RE.test(nxt) && !SIMPLE_NUM_RE.test(nxt)) {
            title = nxt;
            i = j;
          }
          break;
        }
      }
      const raw1 = ch[1];
      openChapter(title, /^\d+$/.test(raw1) ? Number(raw1) : romanToInt(raw1));
      continue;
    }

    const num = line.match(NUMBERED_RE);
    if (num) {
      const parts = num[1].split(".");
      const chapterNo = Number(parts[0]);
      // Kode berawalan nomor bab yang belum dibuka (mis. 2.1 tanpa baris "BAB II"): buka bab baru; judulnya dari struktur saat ini.
      if (!current || chapterNo !== currentNo) openChapter(fallbackChapterTitles[chapterNo - 1] ?? "", chapterNo);
      if (parts.length >= 4) flattened += 1;
      addRow(cleanTitle(num[2]), parts.length >= 3 ? 2 : 1, words);
      continue;
    }

    if (!current) {
      // Baris biasa sebelum bab mana pun: kemungkinan judul dokumen/kop ("DAFTAR ISI"); abaikan.
      continue;
    }

    const simple = line.match(SIMPLE_NUM_RE);
    if (simple) {
      addRow(cleanTitle(simple[2]), 1, words);
      continue;
    }
    const letter = line.match(LETTER_RE);
    if (letter) {
      addRow(cleanTitle(letter[1]), 2, words);
      continue;
    }

    // Tanpa nomor: tingkat dari lekukan (lebih menjorok daripada subbab sebelumnya = anak).
    const indent = indentOf(raw);
    const lastRow: ParsedRow | undefined = (current as ParsedChapter).rows[(current as ParsedChapter).rows.length - 1];
    let level: 1 | 2 = 1;
    if (level1Indent < 0) level1Indent = indent;
    else if (indent > level1Indent + 1 && lastRow) level = 2;
    addRow(cleanTitle(line), level, words);
  }

  const nonEmpty = chapters.filter((c) => c.title || c.rows.length > 0);
  if (nonEmpty.length === 0) warnings.push("Tidak ada bab terdeteksi. Mulai dengan baris seperti \"BAB I PENDAHULUAN\" atau \"1.1 Latar Belakang\".");
  if (nonEmpty.length > MAX_CHAPTERS) warnings.push(`Maksimal ${MAX_CHAPTERS} bab; bab selebihnya diabaikan.`);
  const emptyTitles = nonEmpty.filter((c) => !c.title).length;
  if (emptyTitles > 0) warnings.push(`${emptyTitles} bab belum ada judulnya (tidak tertulis di tempelan); lengkapi setelah diterapkan.`);
  const noRows = nonEmpty.filter((c) => c.rows.length === 0).length;
  if (noRows > 0) warnings.push(`${noRows} bab tanpa subbab; tambahkan subbab setelah diterapkan.`);
  if (flattened > 0) warnings.push(`${flattened} butir tingkat 4 (mis. 2.1.1.1) diratakan menjadi tingkat 3; Skripsa mendukung sampai 2.1.1.`);
  if (promoted > 0) warnings.push(`${promoted} sub-subbab tanpa subbab induk dijadikan subbab.`);
  if (skippedRows > 0) warnings.push(`${skippedRows} butir melewati batas ${MAX_ROWS_PER_CHAPTER} subbab per bab dan diabaikan.`);
  return { chapters: nonEmpty.slice(0, MAX_CHAPTERS), warnings };
}

export const outlineCounts = (o: ParsedOutline) => ({
  chapters: o.chapters.length,
  sections: o.chapters.reduce((a, c) => a + c.rows.filter((r) => r.level === 1).length, 0),
  subsections: o.chapters.reduce((a, c) => a + c.rows.filter((r) => r.level === 2).length, 0),
});
