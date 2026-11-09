import type { CampusTemplate } from "@/lib/templates";
import type { CoverOptions, Profile, ThesisProject } from "@/lib/types";

export const LOGO_MAX_BYTES = 300 * 1024;
const LOGO_MAX_SIDE = 480;

export interface CoverLabels {
  skripsi: string;
  proposal: string;
  submitted: string;
  by: string;
  nim: string;
  program: string;
  faculty: string;
  approvalTitle: string;
  approvalIntro: string;
  advisor1: string;
  advisor2: string;
  originalityTitle: string;
  originalityBody: (name: string, nim: string, program: string, title: string) => string;
  signed: string;
  student: string;
}

export const COVER_LABELS: Record<"id" | "en", CoverLabels> = {
  id: {
    skripsi: "SKRIPSI",
    proposal: "PROPOSAL SKRIPSI",
    submitted: "Diajukan untuk memenuhi salah satu syarat memperoleh gelar",
    by: "Oleh:",
    nim: "NIM",
    program: "PROGRAM STUDI",
    faculty: "FAKULTAS",
    approvalTitle: "LEMBAR PERSETUJUAN",
    approvalIntro: "Skripsi dengan judul di atas telah diperiksa dan disetujui untuk diujikan.",
    advisor1: "Pembimbing I",
    advisor2: "Pembimbing II",
    originalityTitle: "PERNYATAAN KEASLIAN",
    originalityBody: (name, nim, program, title) =>
      `Saya yang bertanda tangan di bawah ini, ${name || BLANK}, NIM ${nim || BLANK}, mahasiswa Program Studi ${program || BLANK}, menyatakan bahwa skripsi berjudul "${title}" adalah karya saya sendiri, bukan hasil plagiarisme, dan semua sumber yang dikutip telah dicantumkan dengan benar. Apabila di kemudian hari terbukti terdapat pelanggaran, saya bersedia menerima sanksi sesuai ketentuan yang berlaku.`,
    signed: "Yang membuat pernyataan,",
    student: "Mahasiswa",
  },
  en: {
    skripsi: "THESIS",
    proposal: "THESIS PROPOSAL",
    submitted: "Submitted in partial fulfillment of the requirements for the degree of",
    by: "By:",
    nim: "Student ID",
    program: "STUDY PROGRAM",
    faculty: "FACULTY OF",
    approvalTitle: "APPROVAL SHEET",
    approvalIntro: "The thesis entitled above has been examined and approved for defense.",
    advisor1: "Advisor I",
    advisor2: "Advisor II",
    originalityTitle: "STATEMENT OF ORIGINALITY",
    originalityBody: (name, nim, program, title) =>
      `I, the undersigned, ${name || BLANK}, student ID ${nim || BLANK}, of the ${program || BLANK} study program, declare that the thesis entitled "${title}" is my own work, free of plagiarism, and that every source cited is properly acknowledged. Should any violation be proven, I accept the sanctions under the prevailing regulations.`,
    signed: "Declared by,",
    student: "Student",
  },
};

export const BLANK = "……………………";

export interface CoverModel {
  lang: "id" | "en";
  labels: CoverLabels;
  docTypeLabel: string;
  title: string;
  degreeLine: string;
  name: string;
  nim: string;
  program: string;
  faculty: string;
  campus: string;
  placeYear: string;
  advisor1: string;
  advisor2: string;
  logo: string | null;
  logoCm: number;
  titlePt: number;
  bodyPt: number;
  caps: boolean;
  titlePage: boolean;
  approval: boolean;
  originality: boolean;
}

/** Gabungkan profil akun, opsi proyek, dan aturan templat menjadi satu model yang dipakai pratinjau dan DOCX. */
export interface CoverInput {
  language: string;
  rules?: CampusTemplate["cover"];
  cover: CoverOptions;
}

export const DEFAULT_COVER_OPTIONS: CoverOptions = {
  advisor1: "",
  advisor2: "",
  docType: "SKRIPSI",
  degreeTitle: "",
  titlePage: true,
  approval: true,
  originality: true,
};

export const coverInputOf = (p: ThesisProject): CoverInput => ({ language: p.form.language, rules: p.template.cover, cover: p.cover });

const stripLead = (v: string | undefined, re: RegExp) => (v ?? "").trim().replace(re, "").trim();

export function resolveCover(input: CoverInput, profile: Profile | null, title: string): CoverModel {
  const lang = input.language === "en" ? "en" : "id";
  const labels = COVER_LABELS[lang];
  const rules = input.rules;
  const c: CoverOptions = input.cover;
  const year = c.year ?? new Date().getFullYear();
  const caps = rules?.caps ?? true;
  return {
    lang,
    labels,
    docTypeLabel: c.docType === "PROPOSAL" ? labels.proposal : labels.skripsi,
    title: caps ? title.toUpperCase() : title,
    degreeLine: `${labels.submitted} ${c.degreeTitle.trim() || BLANK}`,
    name: profile?.fullName.trim() ?? "",
    nim: profile?.nim.trim() ?? "",
    // Label sudah memuat "PROGRAM STUDI"/"FAKULTAS"; buang awalan yang diketik pengguna agar tidak dobel.
    program: stripLead(profile?.majorName, /^(program\s+studi|prodi|study\s+program)\s+/i),
    faculty: stripLead(profile?.faculty, /^(fakultas|faculty\s+of|faculty)\s+/i),
    campus: profile?.campusName.trim() ?? "",
    placeYear: [profile?.city.trim(), String(year)].filter(Boolean).join(" "),
    advisor1: c.advisor1.trim(),
    advisor2: c.advisor2.trim(),
    logo: profile?.logoData ?? null,
    logoCm: c.logoCm ?? rules?.logo_cm ?? 4,
    titlePt: rules?.title_pt ?? 14,
    bodyPt: rules?.body_pt ?? 12,
    caps,
    titlePage: c.titlePage,
    approval: c.approval,
    originality: c.originality,
  };
}

/** Isian profil yang masih kosong dan dibutuhkan sampul. */
export function missingCoverFields(p: Profile | null): string[] {
  if (!p) return ["nama", "NIM", "program studi", "fakultas", "kampus", "logo"];
  const out: string[] = [];
  if (!p.fullName.trim()) out.push("nama");
  if (!p.nim.trim()) out.push("NIM");
  if (!p.majorName.trim()) out.push("program studi");
  if (!p.faculty.trim()) out.push("fakultas");
  if (!p.campusName.trim()) out.push("kampus");
  if (!p.logoData) out.push("logo");
  return out;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Berkas gambar tidak dapat dibaca"));
    img.src = src;
  });
}

/** Ubah gambar apa pun (PNG/JPG/WebP/SVG) menjadi PNG maks 480 px agar ringan dan aman dimasukkan ke DOCX. */
export async function normalizeLogo(file: File): Promise<string> {
  if (!file.type.startsWith("image/")) throw new Error("Pilih berkas gambar (PNG, JPG, atau SVG)");
  if (file.size > 8 * 1024 * 1024) throw new Error("Berkas terlalu besar (maksimal 8 MB)");
  const url = URL.createObjectURL(file);
  try {
    const img = await loadImage(url);
    const w0 = img.naturalWidth || LOGO_MAX_SIDE;
    const h0 = img.naturalHeight || LOGO_MAX_SIDE;
    for (const side of [LOGO_MAX_SIDE, 320, 220]) {
      const scale = Math.min(1, side / Math.max(w0, h0));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(w0 * scale));
      canvas.height = Math.max(1, Math.round(h0 * scale));
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas tidak tersedia");
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/png");
      const bytes = Math.floor(((dataUrl.length - dataUrl.indexOf(",") - 1) * 3) / 4);
      if (bytes <= LOGO_MAX_BYTES) return dataUrl;
    }
    throw new Error("Logo masih terlalu besar setelah dikecilkan; gunakan gambar yang lebih sederhana");
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function imageSize(dataUrl: string): Promise<{ width: number; height: number }> {
  return loadImage(dataUrl).then((i) => ({ width: i.naturalWidth, height: i.naturalHeight }));
}
