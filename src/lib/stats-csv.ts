export interface GroupData {
  name: string;
  values: number[];
}

export type ParsedGroups = { ok: true; groups: GroupData[]; format: "panjang" | "lebar"; skipped: number } | { ok: false; error: string };

const MAX_GROUPS = 12;
const MAX_VALUES = 5000;

function splitLine(line: string, delimiter: RegExp): string[] {
  return line.split(delimiter).map((c) => c.trim().replace(/^"|"$/g, "").trim());
}

function toNumber(cell: string, decimalComma: boolean): number | null {
  if (cell === "") return null;
  const n = Number(decimalComma ? cell.replace(",", ".") : cell);
  return Number.isFinite(n) ? n : null;
}

/**
 * Baca data kelompok dari CSV/TSV hasil Excel.
 *  - format panjang : dua kolom (kelompok, nilai), satu baris per pengamatan
 *  - format lebar   : satu kolom per kelompok (mis. Pre, Post), baris pertama = nama kelompok
 * Titik koma/tab memperbolehkan koma desimal ala Excel Indonesia ("72,5").
 */
export function parseGroupsCsv(text: string): ParsedGroups {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  if (lines.length < 2) return { ok: false, error: "Data terlalu sedikit. Butuh baris judul dan minimal satu baris nilai." };

  const semicolonOrTab = /[;\t]/.test(text);
  const delimiter = semicolonOrTab ? /[;\t]/ : /,/;
  const decimalComma = semicolonOrTab;
  const rows = lines.map((l) => splitLine(l, delimiter));
  const width = Math.max(...rows.map((r) => r.length));
  if (width < 2) return { ok: false, error: "Butuh minimal dua kolom (pisahkan dengan koma, titik koma, atau tab)." };

  const hasHeader = rows[0].some((c) => c !== "" && toNumber(c, decimalComma) === null);
  const header = hasHeader ? rows[0] : [];
  const body = hasHeader ? rows.slice(1) : rows;
  let skipped = 0;
  let groups: GroupData[] = [];
  let format: "panjang" | "lebar";

  const isLong = width === 2 && body.length > 0 && body.every((r) => (r[0] ?? "") === "" || toNumber(r[0], decimalComma) === null);
  if (isLong) {
    format = "panjang";
    const map = new Map<string, number[]>();
    for (const r of body) {
      const label = (r[0] ?? "").trim();
      const v = toNumber(r[1] ?? "", decimalComma);
      if (!label || v === null) {
        skipped++;
        continue;
      }
      map.set(label, [...(map.get(label) ?? []), v]);
    }
    groups = [...map].map(([name, values]) => ({ name, values }));
  } else {
    format = "lebar";
    for (let j = 0; j < width; j++) {
      const values: number[] = [];
      for (const r of body) {
        const cell = r[j] ?? "";
        const v = toNumber(cell, decimalComma);
        if (v === null) {
          if (cell !== "") skipped++;
          continue;
        }
        values.push(v);
      }
      if (values.length > 0) groups.push({ name: header[j]?.trim() || `Kelompok ${j + 1}`, values });
    }
  }

  if (groups.length === 0) return { ok: false, error: "Tidak ada nilai numerik yang terbaca." };
  if (groups.length > MAX_GROUPS) return { ok: false, error: `Maksimal ${MAX_GROUPS} kelompok (terbaca ${groups.length}).` };
  if (groups.some((g) => g.values.length > MAX_VALUES)) return { ok: false, error: `Maksimal ${MAX_VALUES} data per kelompok.` };
  const names = groups.map((g) => g.name);
  if (new Set(names).size !== names.length) return { ok: false, error: "Nama kelompok kembar. Beri nama kolom yang berbeda." };
  return { ok: true, groups, format, skipped };
}

/** Angka ala Indonesia: koma desimal, p-value tiga desimal. */
export function fmtId(n: number, digits = 2): string {
  return new Intl.NumberFormat("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

export function fmtP(p: number): string {
  return p < 0.001 ? "< 0,001" : fmtId(p, 3);
}
