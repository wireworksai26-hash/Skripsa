import type { CitationStyle, DegreeLevel, Method } from "@/lib/types";

/** Templat kampus (format JSON dari Campus Template Engine). Datanya selalu berasal dari server. */
export interface CampusTemplate {
  campus_id: string;
  campus_name: string;
  faculty: string;
  degree_level: DegreeLevel;
  page_setup: {
    paper_size: string;
    margins_cm: { top: number; left: number; bottom: number; right: number };
    font_family: string;
    font_size_pt: number;
    line_spacing: number;
    paragraph_indent_cm: number;
  };
  cover?: {
    logo_cm: number;
    title_pt: number;
    body_pt: number;
    caps: boolean;
    title_page: boolean;
    approval: boolean;
    originality: boolean;
  };
  citation_style: CitationStyle;
  chapters: {
    chapter_number: string;
    chapter_title: string;
    sub_sections: { code: string; title: string; target_words: number }[];
  }[];
  is_custom?: boolean;
}

export interface TemplateSummary {
  campus_id: string;
  campus_name: string;
  degree_level: DegreeLevel;
  research_method?: Method | null;
  citation_style?: CitationStyle | null;
  total_words: number;
  is_custom: boolean;
  source_filename?: string;
}

/** Laporan hasil parsing PDF pedoman: apa yang terbaca dari dokumen dan apa yang memakai nilai bawaan. */
export interface GuidelineReport {
  extracted: string[];
  defaulted: string[];
  warnings: string[];
  evidence: Record<string, { quote: string; verified: boolean }>;
  pages: number;
  pages_used: number;
  provider: string;
  filename: string;
}

export const totalTargetWords = (t: CampusTemplate): number =>
  t.chapters.reduce((a, c) => a + c.sub_sections.reduce((b, s) => b + s.target_words, 0), 0);

/** Sama dengan logika server: jenjang S2 -> templat S2, kualitatif -> templat kualitatif, selain itu kuantitatif. */
export function suggestTemplateId(method: Method, degree: DegreeLevel): string {
  if (degree === "S2") return "nasional-s2-umum";
  if (method === "KUALITATIF") return "nasional-s1-kualitatif";
  if (method === "RND") return "nasional-s1-rnd";
  return "nasional-s1-kuantitatif";
}
