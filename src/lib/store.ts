import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, ApiError, readSession, writeSession, type AuthSession, type ExistingStart } from "@/lib/api";
import { queueEdit } from "@/lib/offline-queue";
import type { TemplateSummary } from "@/lib/templates";
import type {
  AgentReview,
  ChartSpec,
  CoverOptions,
  DiagramSpec,
  InisiasiForm,
  Profile,
  ResultTable,
  ReviseResult,
  Section,
  ThesisProject,
} from "@/lib/types";

/* ---------- sesi login ---------- */

interface AuthState {
  session: AuthSession | null;
  ready: boolean;
  hydrate: () => void;
  signIn: (s: AuthSession) => void;
  signOut: () => void;
}

export const useAuth = create<AuthState>()((set) => ({
  session: null,
  ready: false,
  hydrate: () => set({ session: readSession(), ready: true }),
  signIn: (s) => {
    writeSession(s);
    set({ session: s, ready: true });
  },
  signOut: () => {
    writeSession(null);
    set({ session: null });
    useProject.getState().closeProject();
    useProfile.setState({ profile: null });
  },
}));

/* ---------- profil penulis (data sampul) ---------- */

interface ProfileState {
  profile: Profile | null;
  loading: boolean;
  load: (force?: boolean) => Promise<void>;
  save: (p: Profile) => Promise<void>;
}

export const useProfile = create<ProfileState>()((set, get) => ({
  profile: null,
  loading: false,
  load: async (force = false) => {
    if (get().profile && !force) return;
    set({ loading: true });
    try {
      set({ profile: await api.getProfile() });
    } finally {
      set({ loading: false });
    }
  },
  save: async (p) => {
    set({ profile: await api.updateProfile(p) });
  },
}));

/* ---------- proyek aktif: server adalah sumber kebenaran ---------- */

interface ProjectState {
  /** Satu-satunya yang disimpan di perangkat; isi proyek selalu dimuat dari server. */
  activeId: string | null;
  project: ThesisProject | null;
  loading: boolean;
  templates: TemplateSummary[];

  loadTemplates: () => Promise<void>;
  startProject: (form: InisiasiForm, existing?: ExistingStart) => Promise<void>;
  loadActive: () => Promise<void>;
  closeProject: () => void;
  deleteProject: () => Promise<void>;

  generateTitles: () => Promise<void>;
  pickTitle: (titleId: string) => Promise<void>;
  updateCover: (c: CoverOptions) => Promise<void>;
  /** Muat ulang proyek aktif dari server (mis. setelah struktur bab diubah). */
  reload: () => Promise<void>;
  /** Perbarui bagian proyek yang diubah lewat endpoint khusus (halaman depan, lampiran, tautan). */
  setPart: (part: Partial<Pick<ThesisProject, "front" | "appendices" | "shareToken" | "references" | "selectedRefIds">>) => void;

  searchReferences: (recentOnly?: boolean) => Promise<string[]>;
  selectRecentRefs: (years?: number) => Promise<number>;
  reviseSection: (code: string, feedback: string[], includeImported: boolean) => Promise<ReviseResult>;
  undoSection: (code: string) => Promise<void>;
  openProject: (id: string) => void;
  toggleRef: (refId: string) => Promise<void>;
  selectAllRefs: (on: boolean) => Promise<void>;

  ensureSections: () => Promise<void>;
  generateSection: (code: string, overwrite?: boolean) => Promise<void>;
  editSection: (code: string, content: string) => void;
  persistSection: (code: string) => Promise<void>;

  addChart: (spec: Omit<ChartSpec, "id">) => Promise<void>;
  removeChart: (id: string) => Promise<void>;
  addDiagram: (d: Omit<DiagramSpec, "id">) => Promise<void>;
  removeDiagram: (id: string) => Promise<void>;
  addTable: (t: Omit<ResultTable, "id">) => Promise<void>;
  removeTable: (id: string) => Promise<void>;

  runReview: () => Promise<void>;
}

const MAX_REFS = 15;
const buildInFlight = new Map<string, Promise<Section[]>>();

export const useProject = create<ProjectState>()(
  persist(
    (set, get) => {
      const current = (): ThesisProject => {
        const p = get().project;
        if (!p) throw new Error("Belum ada proyek aktif");
        return p;
      };
      const patch = (fn: (p: ThesisProject) => Partial<ThesisProject>) =>
        set((s) => (s.project ? { project: { ...s.project, ...fn(s.project), updatedAt: Date.now() } } : s));

      return {
        activeId: null,
        project: null,
        loading: false,
        templates: [],

        loadTemplates: async () => {
          set({ templates: await api.listTemplates() });
        },

        startProject: async (form, existing) => {
          const project = await api.createThesis(form, existing);
          set({ project, activeId: project.id });
        },

        loadActive: async () => {
          const { activeId, project } = get();
          if (!activeId || project?.id === activeId) return;
          set({ loading: true });
          try {
            set({ project: await api.loadThesis(activeId) });
          } catch (e) {
            // Proyek sudah dihapus/bukan milik akun ini: lepas, jangan memblokir wizard.
            if (e instanceof ApiError && (e.status === 404 || e.status === 403)) set({ activeId: null, project: null });
            else throw e;
          } finally {
            set({ loading: false });
          }
        },

        closeProject: () => set({ activeId: null, project: null }),

        deleteProject: async () => {
          const p = current();
          await api.deleteThesis(p.id);
          set({ activeId: null, project: null });
        },

        generateTitles: async () => {
          const p = current();
          const { titles, provider } = await api.generateTitles(p.id);
          // Server menghapus opsi judul lama, jadi pilihan lama tidak valid lagi. Pengecualian: judul milik
          // pengguna (mode lanjutan) tetap terkunci dan hanya alternatifnya yang diganti.
          patch((cur) => ({
            titles,
            titlesProvider: provider,
            pickedTitleId: cur.sourceMode === "EXISTING" ? cur.pickedTitleId : undefined,
          }));
        },

        setPart: (part) => patch(() => part),

        reload: async () => {
          const id = get().activeId;
          if (id) set({ project: await api.loadThesis(id) });
        },

        updateCover: async (c) => {
          const p = current();
          const before = p.cover;
          patch(() => ({ cover: c }));
          try {
            await api.updateCover(p.id, c);
          } catch (e) {
            patch(() => ({ cover: before }));
            throw e;
          }
        },

        pickTitle: async (titleId) => {
          const p = current();
          const unpick = p.pickedTitleId === titleId;
          const title = p.titles.find((t) => t.id === titleId) ?? null;
          const before = p.pickedTitleId;
          patch(() => ({ pickedTitleId: unpick ? undefined : titleId }));
          try {
            await api.pickTitle(p.id, unpick ? null : title);
          } catch (e) {
            patch(() => ({ pickedTitleId: before }));
            throw e;
          }
        },

        searchReferences: async (recentOnly = false) => {
          const p = current();
          const query = [p.form.topic, p.form.variableX, p.form.variableY].filter(Boolean).join(" ");
          const { refs, errors } = await api.searchReferences(
            p.id,
            query,
            p.form.domain,
            recentOnly ? new Date().getFullYear() - 4 : undefined
          );
          // Rujukan yang sudah dipilih tidak boleh hilang dari daftar saat pencarian diulang.
          const keep = p.references.filter((r) => p.selectedRefIds.includes(r.id) && !refs.some((n) => n.id === r.id));
          patch(() => ({ references: [...refs, ...keep] }));
          return errors;
        },

        selectRecentRefs: async (years = 5) => {
          const p = current();
          const from = new Date().getFullYear() - years + 1;
          const next = p.references.filter((r) => r.year >= from).slice(0, MAX_REFS).map((r) => r.id);
          patch(() => ({ selectedRefIds: next }));
          try {
            await api.setSelectedRefs(p.id, next);
          } catch (e) {
            patch(() => ({ selectedRefIds: p.selectedRefIds }));
            throw e;
          }
          return next.length;
        },

        reviseSection: async (code, feedback, includeImported) => {
          const p = current();
          const r = await api.reviseSection(p.id, code, feedback, includeImported);
          patch((cur) => ({
            sections: cur.sections.map((s) => (s.sectionCode === code ? { ...s, content: r.content, citations: r.citations } : s)),
          }));
          return r;
        },

        undoSection: async (code) => {
          const p = current();
          const r = await api.undoSection(p.id, code);
          patch((cur) => ({
            sections: cur.sections.map((s) => (s.sectionCode === code ? { ...s, content: r.content, citations: r.citations } : s)),
          }));
        },

        openProject: (id) => set({ activeId: id, project: null }),

        toggleRef: async (refId) => {
          const p = current();
          const has = p.selectedRefIds.includes(refId);
          const next = has ? p.selectedRefIds.filter((r) => r !== refId) : [...p.selectedRefIds, refId].slice(0, MAX_REFS);
          patch(() => ({ selectedRefIds: next }));
          try {
            await api.setSelectedRefs(p.id, next);
          } catch (e) {
            patch(() => ({ selectedRefIds: p.selectedRefIds }));
            throw e;
          }
        },

        selectAllRefs: async (on) => {
          const p = current();
          const next = on ? p.references.slice(0, MAX_REFS).map((r) => r.id) : [];
          patch(() => ({ selectedRefIds: next }));
          try {
            await api.setSelectedRefs(p.id, next);
          } catch (e) {
            patch(() => ({ selectedRefIds: p.selectedRefIds }));
            throw e;
          }
        },

        ensureSections: async () => {
          const p = current();
          if (p.sections.length > 0) return;
          // React Strict Mode memanggil efek dua kali di dev; permintaan yang sama dipakai bersama.
          let job = buildInFlight.get(p.id);
          if (!job) {
            job = api.buildSections(p.id).finally(() => buildInFlight.delete(p.id));
            buildInFlight.set(p.id, job);
          }
          const sections = await job;
          patch(() => ({ sections }));
        },

        generateSection: async (code, overwrite = false) => {
          const p = current();
          const r = await api.generateSection(p.id, code, overwrite);
          patch((cur) => ({
            sections: cur.sections.map((s) =>
              s.sectionCode === code ? { ...s, content: r.content, citations: r.citations, provider: r.provider, origin: "GENERATED" } : s
            ),
          }));
        },

        editSection: (code, content) =>
          patch((cur) => ({
            sections: cur.sections.map((s): Section => (s.sectionCode === code ? { ...s, content } : s)),
          })),

        persistSection: async (code) => {
          const p = current();
          const sec = p.sections.find((s) => s.sectionCode === code);
          if (!sec) return;
          try {
            await api.saveSection(p.id, code, sec.content);
          } catch (e) {
            if (e instanceof ApiError && e.status === 0) {
              queueEdit(p.id, code, sec.content);
              return; // disimpan di perangkat; OfflineSync mengirimnya saat tersambung
            }
            throw e;
          }
        },

        addChart: async (spec) => {
          const p = current();
          const id = await api.addChart(p.id, spec);
          patch((cur) => ({ charts: [...cur.charts, { ...spec, id }] }));
        },

        removeChart: async (id) => {
          const p = current();
          await api.removeChart(p.id, id);
          patch((cur) => ({ charts: cur.charts.filter((c) => c.id !== id) }));
        },

        addDiagram: async (d) => {
          const p = current();
          const id = await api.addDiagram(p.id, d);
          patch((cur) => ({ diagrams: [...cur.diagrams, { ...d, id }] }));
        },

        removeDiagram: async (id) => {
          const p = current();
          await api.removeDiagram(p.id, id);
          patch((cur) => ({ diagrams: cur.diagrams.filter((d) => d.id !== id) }));
        },

        addTable: async (t) => {
          const p = current();
          const id = await api.addTable(p.id, t);
          patch((cur) => ({ tables: [...cur.tables, { ...t, id }] }));
        },

        removeTable: async (id) => {
          const p = current();
          await api.removeTable(p.id, id);
          patch((cur) => ({ tables: cur.tables.filter((x) => x.id !== id) }));
        },

        runReview: async () => {
          const p = current();
          const reviews: AgentReview[] = await api.runReview(p.id);
          patch(() => ({ reviews }));
        },
      };
    },
    {
      name: "skripsi-ai-active",
      version: 2,
      partialize: (s) => ({ activeId: s.activeId }),
    }
  )
);
