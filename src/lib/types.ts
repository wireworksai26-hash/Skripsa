import type { CampusTemplate } from "@/lib/templates";

export type Domain = "INFORMATIKA" | "ENGLISH_EDUCATION" | "UMUM";
export type Method = "KUANTITATIF" | "KUALITATIF" | "MIXED_METHODS" | "RND";
export type CitationStyle = "APA_7TH" | "IEEE" | "CHICAGO" | "HARVARD";
export type DegreeLevel = "S1" | "S2";
/** Bahasa naskah: "id" = Bahasa Indonesia, "en" = English penuh (isi, judul bab, ekspor). */
export type ThesisLanguage = "id" | "en";

export interface InisiasiForm {
  domain: Domain;
  method: Method;
  degreeLevel: DegreeLevel;
  language: ThesisLanguage;
  templateId: string;
  topic: string;
  variableX: string;
  variableY: string;
  subject: string;
}

export interface TitleOption {
  id: string;
  text: string;
  rationale: string;
  gap: string;
}

export interface Reference {
  id: string;
  source: "OpenAlex" | "Crossref" | "DOAJ" | "ERIC" | "CORE" | "SemanticScholar" | "arXiv";
  doi?: string;
  title: string;
  authors: string[];
  year: number;
  journal?: string;
  volumeIssue?: string;
  pages?: string;
  abstract?: string;
  citedBy?: number;
  oaUrl?: string;
}

export type SourceDatabase = Reference["source"];

export interface InlineCitation {
  marker: string;
  referenceId: string;
  snippet: string;
}

export interface Section {
  chapterCode: string;
  sectionCode: string;
  title: string;
  content: string;
  targetWords: number;
  citations: InlineCitation[];
  /** Penyedia LLM yang menulis subbab ini (diisi saat dibuat di sesi ini). */
  provider?: string;
  /** IMPORTED = tulisan pengguna (tidak ditimpa tanpa konfirmasi); GENERATED = ditulis agen. */
  origin?: SectionOrigin;
}

export type SectionOrigin = "IMPORTED" | "GENERATED";
export type StartMode = "NEW" | "EXISTING";

export interface ParsedSection {
  section_code: string;
  title: string;
  content: string;
  words: number;
}

export interface ParsedChapter {
  chapter_code: string;
  chapter_title: string;
  sections: ParsedSection[];
}

export interface ParsedDraft {
  chapters: ParsedChapter[];
  total_words: number;
  warnings: string[];
  filename?: string;
}

export type AgentKind = "ADVISOR" | "EXAMINER" | "GUARDRAIL";
export type NoteKind = "praise" | "warn" | "fix" | "info";

export interface AgentNote {
  kind: NoteKind;
  text: string;
}

export interface AgentReview {
  agent: AgentKind;
  modelName: string;
  notes: AgentNote[];
  done: boolean;
  score?: number;
  breakdown?: ScoreItem[];
  caps?: string[];
}

export interface ScoreItem {
  key: string;
  label: string;
  points: number;
  max: number;
  detail: string;
}

export interface ChartSeries {
  label: string;
  value: number;
}

export interface ChartSpec {
  id: string;
  kind: "bar" | "line" | "pie";
  title: string;
  xlabel?: string;
  ylabel?: string;
  series: ChartSeries[];
  caption: string;
  /** Bab tempat gambar disisipkan; bawaan 4. */
  chapter?: string;
}

export type DiagramEngine = "mermaid" | "plantuml";

export interface DiagramSpec {
  id: string;
  title: string;
  engine: DiagramEngine;
  code: string;
  caption: string;
  /** PNG hasil render Kroki (data URL), dipakai untuk pratinjau dan ekspor DOCX. */
  image?: string;
  width?: number;
  height?: number;
  /** Bab tempat diagram disisipkan (kerangka konseptual = 2, alur analisis = 3). */
  chapter?: string;
}

export interface ResultTable {
  id: string;
  title: string;
  caption: string;
  columns: string[];
  rows: string[][];
  note: string;
  chapter?: string;
}

export interface GroupStats {
  group: string;
  n: number;
  mean: number;
  sd: number;
  se: number;
  min: number;
  max: number;
  median: number;
}

export interface TestResult {
  test: "welch_t" | "paired_t" | "anova";
  name: string;
  statistic: number;
  df: number;
  df2?: number;
  p: number;
  mean_diff?: number;
  effect_size: number | null;
  effect_name: string;
  report: string;
  significant: boolean;
}

export interface StatsResult {
  descriptives: GroupStats[];
  alpha: number;
  test: TestResult | null;
  interpretation: string;
}

/** Identitas penulis untuk sampul; tersimpan di akun dan dipakai semua proyek. */
export interface Profile {
  fullName: string;
  nim: string;
  majorName: string;
  faculty: string;
  campusName: string;
  city: string;
  logoData: string | null;
  notifyPrefs: NotifyPrefs;
  emailVerified?: boolean;
}

export interface NotifyPrefs {
  draft: boolean;
  review: boolean;
  reminder: boolean;
}

/** Opsi sampul per proyek (hal yang berbeda tiap skripsi). */
export interface CoverOptions {
  year?: number;
  advisor1: string;
  advisor2: string;
  docType: "SKRIPSI" | "PROPOSAL";
  degreeTitle: string;
  logoCm?: number;
  titlePage: boolean;
  approval: boolean;
  originality: boolean;
}

export type StatTestKind = "correlation" | "regression" | "chi_square" | "normality" | "reliability";

export interface DataColumn {
  name: string;
  numeric: boolean;
  n: number;
  distinct: number;
}

export interface StatTestResult {
  kind: StatTestKind;
  report: string;
  interpretation: string;
  significant: boolean;
}

export interface ResearchDataItem {
  id: string;
  title: string;
  kind: "table" | "text";
  content: string;
  analyzed: boolean;
  analysis: {
    type?: "table" | "text";
    rows?: number;
    themes?: Array<{ name: string; description: string; excerpts: string[] }>;
    notes?: string;
    tables?: Array<{ title: string }>;
    tests?: Array<{ kind: StatTestKind; report: string; interpretation: string }>;
  };
}

/** Kerangka penelitian yang sudah ditemukan peneliti (mode lanjutan). */
export interface Brief {
  topic: string;
  phenomenon: string;
  problem: string;
  theory: string;
  method: string;
}

export interface AiStyleReport {
  sections: Array<{ code: string; title: string; imported: boolean; words: number; score: number | null; label: string; reasons: string[]; examples: string[] }>;
  overall: number | null;
  overall_label: string | null;
  disclaimer: string;
  note: string;
}

export interface WebCheckReport {
  checked: number;
  errors: number;
  matches: Array<{
    section: string;
    section_title: string;
    own_writing: boolean;
    phrase: string;
    source_title: string;
    source_doi: string | null;
    source_year: number | null;
    other_hits: number;
    in_your_references: boolean;
  }>;
  note: string;
}

export interface CitationAudit {
  style: string;
  references: number;
  in_text_citations: number;
  unknown: Array<{ section: string; title: string; own_writing: boolean; text: string }>;
  year_mismatch: Array<{ section: string; title: string; text: string; listed_years: number[] }>;
  uncited: Array<{ title: string; authors: string[]; year: number }>;
  numeric_out_of_range: Array<{ section: string; text: string; number: number }>;
  duplicates: Array<{ title: string; same_as: string }>;
  weak: { no_authors: string[]; no_year: string[]; no_doi: number };
  style_issues: string[];
  ok: boolean;
}

export interface SlidePlanItem {
  key: string;
  title: string;
  chapter: string;
  bullets: string[];
  notes: string;
}

export interface FrontMatter {
  abstractId: string;
  abstractEn: string;
  keywordsId: string[];
  keywordsEn: string[];
  preface: string;
}

export interface Appendix {
  id: string;
  kind: "kuesioner" | "wawancara" | "validasi";
  title: string;
  intro: string;
  items: string[];
}

export interface ShareComment {
  id: string;
  sectionCode: string;
  author: string;
  text: string;
  resolved: boolean;
  createdAt: string;
}

export interface DefenseResult {
  score: number;
  dimensions: Array<{ key: string; label: string; score: number; max: number; critique: string; verified: boolean }>;
  strength: string;
  improvements: string[];
  betterAnswer: string;
  provider: string;
}

export interface SimilarityReport {
  sections: Array<{ code: string; title: string; peak: number; imported: boolean; flagged: Array<{ excerpt: string; score: number; source: string }> }>;
  overallPeak: number;
  sourcesCompared: number;
  threshold: number;
}

export interface Activity {
  goal: number;
  today: number;
  streak: number;
  total: number;
  series: Array<{ day: string; words: number }>;
}

export interface SectionVersionInfo {
  id: string;
  reason: string;
  createdAt: string;
  content: string;
}

export interface SharedThesis {
  title: string;
  language: string;
  author: string;
  sections: Array<{ code: string; title: string; content: string }>;
  bibliography: string[];
  comments: ShareComment[];
}

export interface ThesisProject {
  id: string;
  form: InisiasiForm;
  templateId: string;
  template: CampusTemplate;
  titles: TitleOption[];
  pickedTitleId?: string;
  titlesProvider?: string;
  sourceMode: StartMode;
  cover: CoverOptions;
  brief: Brief;
  front: FrontMatter | null;
  appendices: Appendix[];
  shareToken: string | null;
  references: Reference[];
  selectedRefIds: string[];
  sections: Section[];
  charts: ChartSpec[];
  diagrams: DiagramSpec[];
  tables: ResultTable[];
  reviews: AgentReview[];
  status: "IN_PROGRESS" | "DRAF_FINAL";
  createdAt: number;
  updatedAt: number;
}

export const DOMAIN_LABEL: Record<Domain, string> = {
  INFORMATIKA: "Teknik Informatika / SI",
  ENGLISH_EDUCATION: "Pendidikan Bahasa Inggris",
  UMUM: "Umum (non-teknis)",
};

export const METHOD_LABEL: Record<Method, string> = {
  KUANTITATIF: "Kuantitatif",
  KUALITATIF: "Kualitatif",
  MIXED_METHODS: "Mixed Methods",
  RND: "R&D (Pengembangan)",
};

export const LANGUAGE_LABEL: Record<ThesisLanguage, string> = {
  id: "Bahasa Indonesia",
  en: "English (full)",
};

export interface ProjectSummary {
  thesis_id: string;
  title: string;
  status: string;
  source_mode: StartMode;
  domain: Domain;
  method: Method;
  degree_level: DegreeLevel;
  template_id: string;
  created_at: string | null;
  updated_at: string | null;
  words: number;
  target_words: number;
  sections_total: number;
  sections_filled: number;
  sections_imported: number;
  refs_selected: number;
  charts: number;
  tables: number;
  revisions: number;
  review: { advisor: number | null; examiner: number | null; guardrail: number | null };
}

export interface ReviseResult {
  content: string;
  citations: InlineCitation[];
  wordCount: number;
  beforeWords: number;
  changes: string[];
  canUndo: boolean;
  provider: string;
}

export interface VisualProposal {
  id: string;
  chapter: string;
  type: "table" | "diagram";
  title: string;
  caption: string;
  columns: string[];
  rows: string[][];
  note: string;
  mermaid: string;
  rationale: string;
  needs_data?: boolean;
  source: "auto" | "ai";
}
