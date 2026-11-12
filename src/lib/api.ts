import type { CampusTemplate, GuidelineReport, TemplateSummary } from "@/lib/templates";
import type {
  AgentKind,
  AgentReview,
  Activity,
  SlidePlanItem,
  CitationAudit,
  AiStyleReport,
  WebCheckReport,
  Brief,
  ResearchDataItem,
  DataColumn,
  StatTestKind,
  StatTestResult,
  Appendix,
  ChartSpec,
  CoverOptions,
  DefenseResult,
  FrontMatter,
  SectionVersionInfo,
  ShareComment,
  SharedThesis,
  SimilarityReport,
  DiagramSpec,
  InisiasiForm,
  InlineCitation,
  NotifyPrefs,
  ParsedDraft,
  Profile,
  ProjectSummary,
  Reference,
  ReviseResult,
  Section,
  ResultTable,
  StatsResult,
  ThesisProject,
  TitleOption,
  VisualProposal,
} from "@/lib/types";

export interface ExistingStart {
  /** Judul milik pengguna; kosong bila hanya bab yang diimpor. */
  title: string;
  sections: Array<{ section_code: string; title: string; content: string }>;
}

export interface SubsectionSuggestions {
  suggestions: Record<string, Array<{ title: string; target_words: number }>>;
  skipped: string[];
  errors: string[];
  provider: string;
}

export interface FoundationalResult {
  found: Array<ServerCitation & { already: boolean; entry: string; note: string }>;
  added: number;
  not_found: Array<{ raw: string; reason: string; closest: { title: string | null; year: number | null; doi: string | null } | null }>;
  unparsed: Array<{ raw: string; reason: string }>;
}

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const AUTH_KEY = "skripsi-ai-auth";

export interface AuthSession {
  token: string;
  userId: string;
  fullName: string;
  email: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
  }
}

export function readSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    return null;
  }
}

export function writeSession(s: AuthSession | null): void {
  try {
    if (s) localStorage.setItem(AUTH_KEY, JSON.stringify(s));
    else localStorage.removeItem(AUTH_KEY);
  } catch {
    /* penyimpanan diblokir: sesi hanya hidup selama tab terbuka */
  }
}

async function request<T>(path: string, init: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (init.auth !== false) {
    const session = readSession();
    if (session) headers.Authorization = `Bearer ${session.token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init.method ?? (init.body !== undefined ? "POST" : "GET"),
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError(`Server tidak terjangkau di ${API_URL}. Pastikan backend FastAPI berjalan.`, 0);
  }

  if (res.status === 401 && init.auth !== false) {
    writeSession(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/masuk")) {
      window.location.href = "/masuk";
    }
  }
  if (!res.ok) {
    let detail = `Permintaan gagal (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail)) {
        detail = j.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || detail;
      }
    } catch {
      /* body bukan JSON */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ---------- bentuk data server ---------- */

interface ServerSection {
  section_code: string;
  chapter_code: string;
  section_title: string;
  content_markdown: string;
  citations_json: Array<{ marker: string; reference_id: string; snippet: string }>;
  target_words: number;
  origin?: string;
}

interface ServerCitation {
  citation_id: string;
  doi: string | null;
  title: string;
  authors: string[];
  publication_year: number;
  journal_name: string | null;
  volume_issue: string | null;
  page_range: string | null;
  pdf_url: string | null;
  highlighted_snippet: string;
  source_database: string;
  cited_by: number;
}

interface ServerTitle {
  title_id: string;
  text: string;
  rationale: string;
  gap: string;
}

interface ServerReview {
  model_name: string;
  notes: Array<{ kind: "praise" | "warn" | "fix" | "info"; text: string }>;
  done: boolean;
  score?: number;
  breakdown?: AgentReview["breakdown"];
  caps?: string[];
}

interface ServerThesis {
  thesis_id: string;
  title: string;
  research_method: InisiasiForm["method"];
  domain_category: InisiasiForm["domain"];
  degree_level: InisiasiForm["degreeLevel"];
  language?: string;
  campus_template_id: string;
  variable_x: string;
  variable_y: string;
  subject: string;
  picked_title_id: string | null;
  selected_ref_ids: string[];
  status: string;
  source_mode?: string;
  brief?: Partial<Brief>;
  front?: { abstract_id?: string; abstract_en?: string; keywords_id?: string[]; keywords_en?: string[]; preface?: string };
  appendix?: Appendix[];
  share_token?: string | null;
  cover?: Partial<{
    year: number | null;
    advisor1: string;
    advisor2: string;
    doc_type: string;
    degree_title: string;
    logo_cm: number | null;
    title_page: boolean;
    approval: boolean;
    originality: boolean;
  }>;
  review_json: Record<string, ServerReview>;
  charts_json: Array<{
    id: string;
    kind: ChartSpec["kind"];
    title: string;
    xlabel?: string;
    ylabel?: string;
    series: ChartSpec["series"];
    caption: string;
    chapter?: string;
  }>;
  diagrams_json: Array<{
    id: string;
    engine?: string;
    title: string;
    code: string;
    caption: string;
    image?: string;
    width?: number;
    height?: number;
    chapter?: string;
  }>;
  tables?: Array<{ table_id: string; title: string; caption: string; columns: string[]; rows: string[][]; note: string; chapter?: string }>;
  sections: ServerSection[];
}

/* ---------- pemetaan ke tipe frontend ---------- */

const mapReference = (c: ServerCitation): Reference => ({
  id: c.citation_id,
  source: c.source_database,
  doi: c.doi ?? undefined,
  title: c.title,
  authors: c.authors,
  year: c.publication_year,
  journal: c.journal_name ?? undefined,
  volumeIssue: c.volume_issue ?? undefined,
  pages: c.page_range ?? undefined,
  abstract: c.highlighted_snippet || undefined,
  citedBy: c.cited_by,
  oaUrl: c.pdf_url ?? undefined,
});

const mapCitation = (c: ServerSection["citations_json"][number]): InlineCitation => ({
  marker: c.marker,
  referenceId: c.reference_id,
  snippet: c.snippet,
});

const mapSection = (s: ServerSection): Section => ({
  chapterCode: s.chapter_code,
  sectionCode: s.section_code,
  title: s.section_title,
  content: s.content_markdown,
  targetWords: s.target_words,
  citations: (s.citations_json ?? []).map(mapCitation),
  origin: s.origin === "IMPORTED" ? "IMPORTED" : "GENERATED",
});

const sortSections = (rows: Section[]) =>
  [...rows].sort((a, b) => a.sectionCode.localeCompare(b.sectionCode, undefined, { numeric: true }));

const mapTitle = (t: ServerTitle): TitleOption => ({
  id: t.title_id,
  text: t.text,
  rationale: t.rationale,
  gap: t.gap,
});

const AGENTS: AgentKind[] = ["ADVISOR", "EXAMINER", "GUARDRAIL"];
const AGENT_NAME: Record<AgentKind, string> = {
  ADVISOR: "Advisor Agent",
  EXAMINER: "Examiner Agent",
  GUARDRAIL: "Quality Guardrail",
};

const mapReview = (agent: AgentKind, r: ServerReview): AgentReview => ({
  agent,
  modelName: r.model_name,
  notes: r.notes,
  done: r.done,
  score: r.score,
  breakdown: r.breakdown,
  caps: r.caps,
});

interface ServerData {
  data_id: string;
  title: string;
  kind: "table" | "text";
  content: string;
  analyzed: boolean;
  analysis: ResearchDataItem["analysis"];
}

const mapData = (d: ServerData): ResearchDataItem => ({ id: d.data_id, title: d.title, kind: d.kind, content: d.content, analyzed: d.analyzed, analysis: d.analysis ?? {} });

const mapFront = (f: ServerThesis["front"]): FrontMatter | null =>
  f && (f.abstract_id || f.abstract_en || f.preface)
    ? { abstractId: f.abstract_id ?? "", abstractEn: f.abstract_en ?? "", keywordsId: f.keywords_id ?? [], keywordsEn: f.keywords_en ?? [], preface: f.preface ?? "" }
    : null;

interface ServerComment {
  comment_id: string;
  section_code: string;
  author: string;
  text: string;
  resolved: boolean;
  created_at: string;
}

const mapComment = (c: ServerComment): ShareComment => ({
  id: c.comment_id,
  sectionCode: c.section_code,
  author: c.author,
  text: c.text,
  resolved: c.resolved,
  createdAt: c.created_at,
});

const frontBody = (f: FrontMatter) => ({
  abstract_id: f.abstractId,
  abstract_en: f.abstractEn,
  keywords_id: f.keywordsId,
  keywords_en: f.keywordsEn,
  preface: f.preface,
});

const mapCover = (c: ServerThesis["cover"], template: CampusTemplate): CoverOptions => ({
  year: c?.year ?? undefined,
  advisor1: c?.advisor1 ?? "",
  advisor2: c?.advisor2 ?? "",
  docType: c?.doc_type === "PROPOSAL" ? "PROPOSAL" : "SKRIPSI",
  degreeTitle: c?.degree_title ?? "",
  logoCm: c?.logo_cm ?? undefined,
  // Belum pernah diatur -> ikuti templat kampus; sudah diatur -> pilihan pengguna.
  titlePage: c?.title_page ?? template.cover?.title_page ?? true,
  approval: c?.approval ?? template.cover?.approval ?? true,
  originality: c?.originality ?? template.cover?.originality ?? true,
});

interface ServerProfile {
  full_name: string;
  nim: string;
  major_name: string;
  faculty: string;
  campus_name: string;
  city: string;
  logo_data: string | null;
  notify_prefs: Partial<NotifyPrefs> | null;
  email_verified?: boolean;
}

const mapProfile = (u: ServerProfile): Profile => ({
  fullName: u.full_name,
  nim: u.nim ?? "",
  majorName: u.major_name,
  faculty: u.faculty ?? "",
  campusName: u.campus_name,
  city: u.city ?? "",
  logoData: u.logo_data ?? null,
  notifyPrefs: { draft: true, review: true, reminder: true, ...(u.notify_prefs ?? {}) },
  emailVerified: u.email_verified ?? false,
});

function mapThesis(
  t: ServerThesis,
  titles: ServerTitle[],
  citations: ServerCitation[],
  template: CampusTemplate
): ThesisProject {
  return {
    id: t.thesis_id,
    form: {
      domain: t.domain_category,
      method: t.research_method,
      degreeLevel: t.degree_level,
      language: t.language === "en" ? "en" : "id",
      templateId: t.campus_template_id,
      topic: t.title,
      variableX: t.variable_x,
      variableY: t.variable_y,
      subject: t.subject,
    },
    templateId: t.campus_template_id,
    template,
    titles: titles.map(mapTitle),
    pickedTitleId: t.picked_title_id || undefined,
    references: citations.map(mapReference),
    selectedRefIds: t.selected_ref_ids ?? [],
    sections: sortSections(t.sections.map(mapSection)),
    charts: (t.charts_json ?? []).map((c) => ({
      id: c.id,
      kind: c.kind,
      title: c.title,
      xlabel: c.xlabel,
      ylabel: c.ylabel,
      series: c.series,
      caption: c.caption,
      chapter: c.chapter ?? "4",
    })),
    diagrams: (t.diagrams_json ?? []).map((d) => ({
      id: d.id,
      title: d.title,
      engine: d.engine === "plantuml" ? ("plantuml" as const) : ("mermaid" as const),
      code: d.code,
      caption: d.caption,
      image: d.image,
      width: d.width,
      height: d.height,
      chapter: d.chapter ?? "4",
    })),
    tables: (t.tables ?? []).map((x) => ({
      id: x.table_id,
      title: x.title,
      caption: x.caption,
      columns: x.columns,
      rows: x.rows,
      note: x.note,
      chapter: x.chapter ?? "4",
    })),
    reviews: AGENTS.map((a) =>
      t.review_json?.[a]
        ? mapReview(a, t.review_json[a])
        : { agent: a, modelName: AGENT_NAME[a], notes: [], done: false }
    ),
    sourceMode: t.source_mode === "EXISTING" ? "EXISTING" : "NEW",
    cover: mapCover(t.cover, template),
    brief: { topic: t.brief?.topic ?? "", phenomenon: t.brief?.phenomenon ?? "", problem: t.brief?.problem ?? "", theory: t.brief?.theory ?? "", method: t.brief?.method ?? "" },
    front: mapFront(t.front),
    appendices: t.appendix ?? [],
    shareToken: t.share_token ?? null,
    status: t.status === "DRAF_FINAL" ? "DRAF_FINAL" : "IN_PROGRESS",
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
}

/* ---------- endpoint ---------- */

interface TokenOut {
  access_token: string;
  user_id: string;
  full_name: string;
  email: string;
}

const toSession = (t: TokenOut): AuthSession => ({
  token: t.access_token,
  userId: t.user_id,
  fullName: t.full_name,
  email: t.email,
});

export const api = {
  login: async (email: string, password: string) =>
    toSession(await request<TokenOut>("/auth/login", { body: { email, password }, auth: false })),

  register: async (p: { fullName: string; email: string; password: string; majorName: string; campusName: string }) =>
    toSession(
      await request<TokenOut>("/auth/register", {
        auth: false,
        body: {
          full_name: p.fullName,
          email: p.email,
          password: p.password,
          major_name: p.majorName,
          campus_name: p.campusName,
        },
      })
    ),

  health: () =>
    request<{
      status: string;
      llm_mode: string;
      llm: { providers: Record<string, boolean>; models: Record<string, string>; routing: { fast: string[]; heavy: string[] } };
      scientific_apis: Record<string, number | string>;
      unpaywall: boolean;
    }>("/health", { auth: false }),

  createThesis: async (form: InisiasiForm, existing?: ExistingStart, brief?: Brief): Promise<ThesisProject> => {
    const t = await request<ServerThesis>("/theses", {
      body: {
        ...(existing
          ? {
              existing_title: existing.title || undefined,
              imported_sections: existing.sections.map((s) => ({ section_code: s.section_code, title: s.title, content: s.content })),
            }
          : {}),
        topic: form.topic,
        variable_x: form.variableX,
        variable_y: form.variableY,
        subject: form.subject,
        method: form.method,
        domain: form.domain,
        degree_level: form.degreeLevel,
        language: form.language,
        template_id: form.templateId,
        ...(brief ? { brief } : {}),
      },
    });
    // Mode lanjutan: server sudah membuat opsi judul milik pengguna; ambil agar kartu "judul terkunci" terisi.
    const [template, titles] = await Promise.all([
      request<CampusTemplate>(`/templates/${t.campus_template_id}?language=${t.language ?? "id"}`),
      t.picked_title_id ? request<ServerTitle[]>(`/theses/${t.thesis_id}/titles`) : Promise.resolve([] as ServerTitle[]),
    ]);
    return mapThesis(t, titles, [], template);
  },

  extractTitle: (title: string) =>
    request<{
      variable_x: string;
      variable_y: string;
      subject: string;
      method: InisiasiForm["method"] | null;
      domain: InisiasiForm["domain"];
      note: string;
      provider: string;
    }>("/import/extract-title", { body: { title } }),

  parseDraftText: (text: string) => request<ParsedDraft>("/import/parse-text", { body: { text } }),

  parseDraftFile: async (file: File): Promise<ParsedDraft> => {
    const form = new FormData();
    form.append("file", file);
    const session = readSession();
    let res: Response;
    try {
      res = await fetch(`${API_URL}/import/parse-file`, {
        method: "POST",
        headers: session ? { Authorization: `Bearer ${session.token}` } : {},
        body: form,
      });
    } catch {
      throw new ApiError(`Server tidak terjangkau di ${API_URL}.`, 0);
    }
    if (!res.ok) {
      let detail = `Naskah tidak dapat dibaca (${res.status})`;
      try {
        const j = await res.json();
        if (typeof j.detail === "string") detail = j.detail;
      } catch {
        /* bukan JSON */
      }
      throw new ApiError(detail, res.status);
    }
    return res.json();
  },

  loadThesis: async (id: string): Promise<ThesisProject> => {
    const [t, titles, citations] = await Promise.all([
      request<ServerThesis>(`/theses/${id}`),
      request<ServerTitle[]>(`/theses/${id}/titles`),
      request<ServerCitation[]>(`/theses/${id}/citations`),
    ]);
    const template = await request<CampusTemplate>(`/templates/${t.campus_template_id}?language=${t.language ?? "id"}`);
    return mapThesis(t, titles, citations, template);
  },

  listTemplates: async (): Promise<TemplateSummary[]> =>
    (await request<{ templates: TemplateSummary[] }>("/templates")).templates,

  getTemplate: (id: string, language: InisiasiForm["language"] = "id") =>
    request<CampusTemplate>(`/templates/${id}?language=${language}`),

  parseGuideline: async (
    file: File,
    degree: string,
    method: string
  ): Promise<{ template: CampusTemplate; report: GuidelineReport }> => {
    const form = new FormData();
    form.append("file", file);
    form.append("degree_hint", degree);
    form.append("method_hint", method);
    const session = readSession();
    let res: Response;
    try {
      res = await fetch(`${API_URL}/templates/parse`, {
        method: "POST",
        headers: session ? { Authorization: `Bearer ${session.token}` } : {},
        body: form,
      });
    } catch {
      throw new ApiError(`Server tidak terjangkau di ${API_URL}.`, 0);
    }
    if (!res.ok) {
      let detail = `Pedoman tidak dapat dibaca (${res.status})`;
      try {
        const j = await res.json();
        if (typeof j.detail === "string") detail = j.detail;
      } catch {
        /* bukan JSON */
      }
      throw new ApiError(detail, res.status);
    }
    return res.json();
  },

  saveCustomTemplate: (p: { template: CampusTemplate; name: string; filename: string; report: GuidelineReport }) =>
    request<TemplateSummary>("/templates/custom", {
      body: { template: p.template, name: p.name, source_filename: p.filename, report: p.report },
    }),

  deleteTemplate: (id: string) => request<void>(`/templates/${id}`, { method: "DELETE" }),

  deleteThesis: (id: string) => request<void>(`/theses/${id}`, { method: "DELETE" }),

  generateTitles: async (id: string): Promise<{ titles: TitleOption[]; provider: string }> => {
    const r = await request<{ provider: string; titles: ServerTitle[] }>(`/theses/${id}/titles`, {
      method: "POST",
      body: {},
    });
    return { titles: r.titles.map(mapTitle), provider: r.provider };
  },

  generateFront: async (id: string): Promise<{ front: FrontMatter; provider: string }> => {
    const r = await request<{ front: NonNullable<ServerThesis["front"]>; provider: string }>(`/theses/${id}/front-matter/generate`, { method: "POST", body: {} });
    return { front: mapFront(r.front)!, provider: r.provider };
  },
  saveFront: (id: string, f: FrontMatter) => request(`/theses/${id}/front-matter`, { method: "PUT", body: frontBody(f) }),

  generateAppendices: async (id: string): Promise<{ appendices: Appendix[]; provider: string }> =>
    request(`/theses/${id}/appendices/generate`, { method: "POST", body: {} }),
  saveAppendices: async (id: string, items: Appendix[]): Promise<Appendix[]> =>
    (await request<{ appendices: Appendix[] }>(`/theses/${id}/appendices`, { method: "PUT", body: items })).appendices,

  importRefs: (id: string, text: string) =>
    request<{ added: number; skipped_duplicates: number; without_year: number; without_authors: number }>(`/theses/${id}/citations/import`, { method: "POST", body: { text } }),
  foundationalRefs: (id: string) => request<FoundationalResult>(`/theses/${id}/citations/foundational`, { method: "POST", body: {} }),
  exportRefs: async (id: string, format: "bibtex" | "ris", selectedOnly: boolean): Promise<Blob> => {
    const session = readSession();
    let res: Response;
    try {
      res = await fetch(`${API_URL}/theses/${id}/citations/export?format=${format}&selected_only=${selectedOnly}`, { headers: session ? { Authorization: `Bearer ${session.token}` } : {} });
    } catch {
      throw new ApiError(`Server tidak terjangkau di ${API_URL}.`, 0);
    }
    if (!res.ok) throw new ApiError(`Ekspor gagal (${res.status})`, res.status);
    return res.blob();
  },

  evaluateDefense: async (id: string, question: string, answer: string): Promise<DefenseResult> => {
    const r = await request<{
      score: number;
      dimensions: Array<{ key: string; label: string; score: number; max: number; critique: string; verified: boolean }>;
      strength: string;
      improvements: string[];
      better_answer: string;
      provider: string;
    }>(`/theses/${id}/defense/evaluate`, { method: "POST", body: { question, answer } });
    return { score: r.score, dimensions: r.dimensions, strength: r.strength, improvements: r.improvements, betterAnswer: r.better_answer, provider: r.provider };
  },

  similarity: async (id: string): Promise<SimilarityReport> => {
    const r = await request<{ sections: SimilarityReport["sections"]; overall_peak: number; sources_compared: number; threshold: number }>(`/theses/${id}/similarity`);
    return { sections: r.sections, overallPeak: r.overall_peak, sourcesCompared: r.sources_compared, threshold: r.threshold };
  },

  sectionVersions: async (id: string, code: string): Promise<SectionVersionInfo[]> =>
    (await request<Array<{ version_id: string; reason: string; created_at: string; content: string }>>(`/theses/${id}/sections/${code}/versions`)).map((v) => ({
      id: v.version_id,
      reason: v.reason,
      createdAt: v.created_at,
      content: v.content,
    })),

  createShare: async (id: string): Promise<string> => (await request<{ token: string }>(`/theses/${id}/share`, { method: "POST", body: {} })).token,
  revokeShare: (id: string) => request(`/theses/${id}/share`, { method: "DELETE" }),
  listComments: async (id: string): Promise<ShareComment[]> => (await request<ServerComment[]>(`/theses/${id}/comments`)).map(mapComment),
  resolveComment: (id: string, commentId: string, resolved: boolean) => request(`/theses/${id}/comments/${commentId}`, { method: "PATCH", body: { resolved } }),
  readShared: async (token: string): Promise<SharedThesis> => {
    const r = await request<Omit<SharedThesis, "comments"> & { comments: ServerComment[] }>(`/share/${token}`, { auth: false });
    return { ...r, comments: r.comments.map(mapComment) };
  },
  addSharedComment: (token: string, body: { section_code: string; author: string; text: string }) =>
    request(`/share/${token}/comments`, { method: "POST", body, auth: false }),

  getActivity: () => request<Activity>("/activity"),
  setDailyGoal: (goal: number) => request<Activity>("/activity/goal", { method: "PUT", body: { daily_goal: goal } }),

  saveStructure: (
    id: string,
    chapters: Array<{ title: string; sections: Array<{ code: string | null; title: string; target_words: number; level: 1 | 2 }> }>,
    confirmDelete: boolean
  ) => request(`/theses/${id}/structure`, { method: "PUT", body: { chapters, confirm_delete: confirmDelete } }),

  suggestSubsections: (id: string, chapters: string[]) =>
    request<SubsectionSuggestions>(`/theses/${id}/structure/suggest`, { method: "POST", body: { chapters } }),

  listData: async (id: string): Promise<ResearchDataItem[]> => (await request<ServerData[]>(`/theses/${id}/data`)).map(mapData),
  addData: async (id: string, d: { title: string; kind: "table" | "text"; content: string }): Promise<ResearchDataItem> =>
    mapData(await request<ServerData>(`/theses/${id}/data`, { method: "POST", body: d })),
  dataColumns: (id: string, dataId: string) => request<DataColumn[]>(`/theses/${id}/data/${dataId}/columns`),
  runStatTest: async (
    id: string,
    dataId: string,
    body: { kind: StatTestKind; a?: string; b?: string; y?: string; xs: string[]; items: string[]; column?: string }
  ): Promise<StatTestResult> => (await request<{ result: StatTestResult }>(`/theses/${id}/data/${dataId}/test`, { method: "POST", body })).result,
  deleteData: (id: string, dataId: string) => request(`/theses/${id}/data/${dataId}`, { method: "DELETE" }),
  analyzeData: async (id: string, dataId: string): Promise<{ data: ResearchDataItem; provider: string }> => {
    const r = await request<{ data: ServerData; provider: string }>(`/theses/${id}/data/${dataId}/analyze`, { method: "POST", body: {} });
    return { data: mapData(r.data), provider: r.provider };
  },

  updateBrief: (id: string, brief: Brief) => request(`/theses/${id}`, { method: "PATCH", body: { brief } }),

  slidePlan: (id: string) => request<{ slides: SlidePlanItem[]; provider: string }>(`/theses/${id}/slides/plan`, { method: "POST", body: {} }),
  citationAudit: (id: string) => request<CitationAudit>(`/theses/${id}/citation-audit`),
  aiStyle: (id: string) => request<AiStyleReport>(`/theses/${id}/integrity/ai-style`),
  webCheck: (id: string) => request<WebCheckReport>(`/theses/${id}/integrity/web`, { method: "POST", body: {} }),

  changePassword: (current: string, next: string) => request("/auth/password", { method: "PUT", body: { current_password: current, new_password: next } }),
  exportMyData: async (): Promise<Blob> => {
    const session = readSession();
    let res: Response;
    try {
      res = await fetch(`${API_URL}/auth/export`, { headers: session ? { Authorization: `Bearer ${session.token}` } : {} });
    } catch {
      throw new ApiError(`Server tidak terjangkau di ${API_URL}.`, 0);
    }
    if (!res.ok) throw new ApiError(`Ekspor gagal (${res.status})`, res.status);
    return res.blob();
  },
  deleteAccount: (password: string) => request("/auth/account", { method: "DELETE", body: { password } }),
  forgotPassword: (email: string) => request("/auth/forgot", { body: { email }, auth: false }),
  resetPassword: (token: string, password: string) => request("/auth/reset", { body: { token, password }, auth: false }),
  sendVerification: () => request("/auth/send-verification", { method: "POST", body: {} }),
  verifyEmail: (token: string) => request("/auth/verify", { body: { token }, auth: false }),

  getProfile: async (): Promise<Profile> => mapProfile(await request<ServerProfile>("/auth/me")),

  updateProfile: async (p: Profile): Promise<Profile> =>
    mapProfile(
      await request<ServerProfile>("/auth/profile", {
        method: "PUT",
        body: {
          full_name: p.fullName,
          nim: p.nim,
          major_name: p.majorName,
          faculty: p.faculty,
          campus_name: p.campusName,
          city: p.city,
          logo_data: p.logoData,
          notify_prefs: p.notifyPrefs,
        },
      })
    ),

  updateCover: (id: string, c: CoverOptions) =>
    request(`/theses/${id}`, {
      method: "PATCH",
      body: {
        cover: {
          year: c.year ?? null,
          advisor1: c.advisor1,
          advisor2: c.advisor2,
          doc_type: c.docType,
          degree_title: c.degreeTitle,
          logo_cm: c.logoCm ?? null,
          title_page: c.titlePage,
          approval: c.approval,
          originality: c.originality,
        },
      },
    }),

  pickTitle: (id: string, title: TitleOption | null) =>
    request(`/theses/${id}`, {
      method: "PATCH",
      body: title ? { picked_title_id: title.id, title: title.text } : { picked_title_id: "" },
    }),

  searchReferences: async (
    id: string,
    query: string,
    domain: string,
    sinceYear?: number
  ): Promise<{ refs: Reference[]; errors: string[] }> => {
    const found = await request<{ refs: Array<Omit<ServerCitation, "citation_id">>; errors: string[] }>(
      "/references/search",
      { body: { query, domain, ...(sinceYear ? { since_year: sinceYear } : {}) } }
    );
    if (found.refs.length === 0) return { refs: [], errors: found.errors };
    const saved = await request<ServerCitation[]>(`/theses/${id}/citations`, { body: found.refs });
    return { refs: saved.map(mapReference), errors: found.errors };
  },

  planVisuals: (id: string, chapters: string[], extra: string) =>
    request<{ items: VisualProposal[]; provider: string }>(`/theses/${id}/visuals/plan`, { body: { chapters, extra } }),

  listProjects: () => request<ProjectSummary[]>("/theses"),

  reviseSection: async (id: string, code: string, feedback: string[], includeImported: boolean): Promise<ReviseResult> => {
    const r = await request<{
      content_markdown: string;
      citations_json: ServerSection["citations_json"];
      word_count: number;
      before_words: number;
      changes: string[];
      can_undo: boolean;
      provider: string;
    }>(`/theses/${id}/sections/${encodeURIComponent(code)}/revise`, { body: { feedback, include_imported: includeImported } });
    return {
      content: r.content_markdown,
      citations: r.citations_json.map(mapCitation),
      wordCount: r.word_count,
      beforeWords: r.before_words,
      changes: r.changes ?? [],
      canUndo: r.can_undo,
      provider: r.provider,
    };
  },

  undoSection: async (id: string, code: string) => {
    const r = await request<{ content_markdown: string; citations_json: ServerSection["citations_json"]; can_undo: boolean }>(
      `/theses/${id}/sections/${encodeURIComponent(code)}/undo`,
      { method: "POST", body: {} }
    );
    return { content: r.content_markdown, citations: r.citations_json.map(mapCitation), canUndo: r.can_undo };
  },

  setSelectedRefs: (id: string, ids: string[]) =>
    request(`/theses/${id}`, { method: "PATCH", body: { selected_ref_ids: ids } }),

  buildSections: async (id: string): Promise<Section[]> => {
    await request(`/theses/${id}/sections/build`, { method: "POST", body: {} });
    const rows = await request<ServerSection[]>(`/theses/${id}/sections`);
    return sortSections(rows.map(mapSection));
  },

  generateSection: async (
    id: string,
    code: string,
    overwrite = false,
    extend = false
  ): Promise<{ content: string; citations: InlineCitation[]; provider: string }> => {
    const r = await request<{
      content_markdown: string;
      citations_json: ServerSection["citations_json"];
      provider: string;
    }>(`/theses/${id}/sections/${encodeURIComponent(code)}/generate?${[overwrite ? "overwrite=true" : "", extend ? "extend=true" : ""].filter(Boolean).join("&")}`, { method: "POST", body: {} });
    return { content: r.content_markdown, citations: r.citations_json.map(mapCitation), provider: r.provider };
  },

  saveSection: (id: string, code: string, content: string) =>
    request(`/theses/${id}/sections/${encodeURIComponent(code)}`, {
      method: "PATCH",
      body: { content_markdown: content },
    }),

  addChart: async (id: string, spec: Omit<ChartSpec, "id">): Promise<string> => {
    const r = await request<{ ok: boolean; chart_id?: string; detail?: string }>(`/theses/${id}/charts`, {
      body: spec,
    });
    if (!r.ok || !r.chart_id) throw new ApiError(r.detail ?? "Grafik ditolak server", 422);
    return r.chart_id;
  },

  removeChart: (id: string, chartId: string) => request(`/theses/${id}/charts/${chartId}`, { method: "DELETE" }),

  addDiagram: async (id: string, d: Omit<DiagramSpec, "id">): Promise<string> =>
    (await request<{ diagram_id: string }>(`/theses/${id}/diagrams`, { body: d })).diagram_id,

  removeDiagram: (id: string, diagramId: string) =>
    request(`/theses/${id}/diagrams/${diagramId}`, { method: "DELETE" }),

  fetchCitationPdf: async (thesisId: string, citationId: string): Promise<ArrayBuffer> => {
    const session = readSession();
    let res: Response;
    try {
      res = await fetch(`${API_URL}/theses/${thesisId}/citations/${citationId}/pdf`, {
        headers: session ? { Authorization: `Bearer ${session.token}` } : {},
      });
    } catch {
      throw new ApiError(`Server tidak terjangkau di ${API_URL}.`, 0);
    }
    if (!res.ok) {
      let detail = `PDF tidak dapat dimuat (${res.status})`;
      try {
        const j = await res.json();
        if (typeof j.detail === "string") detail = j.detail;
      } catch {
        /* bukan JSON */
      }
      throw new ApiError(detail, res.status);
    }
    return res.arrayBuffer();
  },

  analyzeStats: (groups: Array<{ name: string; values: number[] }>, paired: boolean, alpha: number) =>
    request<StatsResult>("/stats/analyze", { body: { groups, paired, alpha } }),

  addTable: async (id: string, t: Omit<ResultTable, "id">): Promise<string> =>
    (await request<{ table_id: string }>(`/theses/${id}/tables`, { body: t })).table_id,

  removeTable: (id: string, tableId: string) => request<void>(`/theses/${id}/tables/${tableId}`, { method: "DELETE" }),

  runReview: async (id: string): Promise<AgentReview[]> => {
    const r = await request<{ reviews: Record<string, ServerReview> }>(`/theses/${id}/review`, {
      method: "POST",
      body: {},
    });
    return AGENTS.map((a) => mapReview(a, r.reviews[a]));
  },
};
