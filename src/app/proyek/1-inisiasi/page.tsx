"use client";

import { askConfirm } from "@/components/ui/confirm";
import { CoverCard } from "@/components/cover/cover-card";
import { BriefCard } from "@/components/wizard/brief-card";
import { BriefFields, briefFilled, EMPTY_BRIEF } from "@/components/wizard/brief-fields";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldHint, Input, Label, Select, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { DraftImport } from "@/components/wizard/draft-import";
import { GuidelineUpload } from "@/components/wizard/guideline-upload";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import { suggestTemplateId, totalTargetWords, type CampusTemplate } from "@/lib/templates";
import { DOMAIN_LABEL, LANGUAGE_LABEL, METHOD_LABEL } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ArrowRight, Loader2, MapPin, Sparkles, Trash2, Wand2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { DegreeLevel, Domain, InisiasiForm, Method, ParsedDraft, StartMode, ThesisLanguage } from "@/lib/types";

const DOMAINS: Domain[] = ["INFORMATIKA", "ENGLISH_EDUCATION", "UMUM"];
const METHODS: Method[] = ["KUANTITATIF", "KUALITATIF", "MIXED_METHODS", "RND"];
const LANGUAGES: ThesisLanguage[] = ["id", "en"];

const EMPTY: InisiasiForm = {
  domain: "UMUM",
  method: "KUANTITATIF",
  degreeLevel: "S1",
  language: "id",
  templateId: "nasional-s1-kuantitatif",
  topic: "",
  variableX: "",
  variableY: "",
  subject: "",
};

export default function InisiasiPage() {
  const router = useRouter();
  const project = useProject((s) => s.project);
  const startProject = useProject((s) => s.startProject);
  const closeProject = useProject((s) => s.closeProject);
  const templates = useProject((s) => s.templates);
  const loadTemplates = useProject((s) => s.loadTemplates);

  const [preview, setPreview] = useState<CampusTemplate | null>(null);
  const [form, setForm] = useState<InisiasiForm>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<StartMode>("NEW");
  const [imported, setImported] = useState<ParsedDraft | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [brief, setBrief] = useState(EMPTY_BRIEF);

  const existing = mode === "EXISTING";
  const [extracting, setExtracting] = useState(false);
  const [extractMsg, setExtractMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const extractFromTitle = async () => {
    setExtracting(true);
    setExtractMsg(null);
    try {
      const r = await api.extractTitle(form.topic.trim());
      setForm((f) => {
        const method = r.method ?? f.method;
        const usingCustom = templates.find((t) => t.campus_id === f.templateId)?.is_custom;
        return {
          ...f,
          variableX: r.variable_x || f.variableX,
          variableY: r.variable_y,
          subject: r.subject || f.subject,
          domain: r.domain,
          method,
          templateId: usingCustom ? f.templateId : suggestTemplateId(method, f.degreeLevel),
        };
      });
      const filled = [
        r.method ? `metode ${METHOD_LABEL[r.method]}` : null,
        `jurusan ${DOMAIN_LABEL[r.domain]}`,
      ].filter(Boolean);
      setExtractMsg({
        kind: "ok",
        text: `Terisi dari judul (oleh ${r.provider}): variabel X, Y, subjek, ${filled.join(", ")}. Periksa dan sesuaikan.${r.note ? ` Catatan: ${r.note}` : ""}`,
      });
    } catch (e) {
      setExtractMsg({ kind: "error", text: e instanceof Error ? e.message : "Ekstraksi gagal" });
    } finally {
      setExtracting(false);
    }
  };

  const set = <K extends keyof InisiasiForm>(key: K, value: InisiasiForm[K]) => {
    setForm((f) => {
      const next = { ...f, [key]: value };
      const usingCustom = templates.find((t) => t.campus_id === f.templateId)?.is_custom;
      if ((key === "method" || key === "degreeLevel") && !usingCustom) {
        next.templateId = suggestTemplateId(next.method, next.degreeLevel);
      }
      return next;
    });
  };

  useEffect(() => {
    loadTemplates().catch((e) => setError(e instanceof Error ? e.message : "Gagal memuat templat"));
  }, [loadTemplates]);

  useEffect(() => {
    let cancelled = false;
    api
      .getTemplate(form.templateId, form.language)
      .then((t) => !cancelled && setPreview(t))
      .catch(() => !cancelled && setPreview(null));
    return () => {
      cancelled = true;
    };
  }, [form.templateId, form.language]);

  const template = preview;
  const selectedSummary = templates.find((t) => t.campus_id === form.templateId);

  const removeCustom = async () => {
    if (!selectedSummary?.is_custom || !(await askConfirm(`Hapus templat "${selectedSummary.campus_name}"?`, { danger: true }))) return;
    try {
      await api.deleteTemplate(selectedSummary.campus_id);
      await loadTemplates();
      setForm((f) => ({ ...f, templateId: suggestTemplateId(f.method, f.degreeLevel) }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menghapus templat");
    }
  };
  const valid =
    form.topic.trim().length >= 15 &&
    form.subject.trim().length >= 3 &&
    form.variableX.trim().length >= 2;

  const handleSubmit = async () => {
    setBusy(true);
    setError(null);
    try {
      await startProject(
        form,
        existing
          ? {
              title: form.topic.trim(),
              sections: (imported?.chapters ?? []).flatMap((c) =>
                c.sections.map((x) => ({ section_code: x.section_code, title: x.title, content: x.content }))
              ),
            }
          : undefined,
        existing && advanced && briefFilled(brief) ? brief : undefined
      );
      router.push("/proyek/2-judul");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membuat proyek");
    } finally {
      setBusy(false);
    }
  };

  if (project) {
    const f = project.form;
    return (
      <div className="space-y-6">
      <Card>
        <div className="flex items-center gap-2">
          <Pill tone="blue">Proyek aktif</Pill>
          <Pill>Tersimpan di server</Pill>
          {project.sourceMode === "EXISTING" && <Pill tone="coral">Dilanjutkan dari naskah sendiri</Pill>}
        </div>
        <h1 className="t-heading mt-4">{project.titles.find((t) => t.id === project.pickedTitleId)?.text ?? f.topic}</h1>
        <dl className="mt-4 grid gap-x-8 gap-y-2 text-[13px] sm:grid-cols-2">
          {[
            ["Jurusan", DOMAIN_LABEL[f.domain]],
            ["Metode", `${METHOD_LABEL[f.method]} · ${f.degreeLevel}`],
            ["Bahasa skripsi", LANGUAGE_LABEL[f.language]],
            ["Variabel X", f.variableX || "—"],
            ["Variabel Y", f.variableY || "—"],
            ["Lokasi / subjek", f.subject || "—"],
            ["Templat", project.template.campus_name],
            ...(project.sourceMode === "EXISTING"
              ? [["Tulisan Anda", `${project.sections.filter((x) => x.origin === "IMPORTED").length} subbab diimpor`]]
              : []),
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 border-b border-dashed border-hairline pb-2">
              <dt className="text-black/50">{k}</dt>
              <dd className="text-right font-medium">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button size="lg" onClick={() => router.push("/proyek/2-judul")}>
            Lanjutkan <ArrowRight size={16} />
          </Button>
          <Button variant="ghost" onClick={() => closeProject()}>
            Mulai proyek baru
          </Button>
        </div>
      </Card>
      <BriefCard />
      <CoverCard />
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card>
        <div className="flex items-center gap-2">
          <Pill tone="blue">
            <Sparkles size={12} /> Promptless Input
          </Pill>
          <Pill>Langkah 1 dari 6</Pill>
        </div>
        <h1 className="t-heading mt-4">{existing ? "Lanjutkan dari naskah yang sudah ada" : "Isi formulir — tanpa menyusun prompt"}</h1>
        <p className="t-serif-lede mt-2 text-graphite">
          {existing
            ? "Judul Anda langsung dikunci, dan bab yang sudah ditulis diimpor sebagai tulisan Anda. Agen hanya melengkapi bagian yang masih kosong."
            : "Backend Prompt Orchestrator merangkai entri ini menjadi instruksi akademis tertata: piramida terbalik Bab 1, kriteria research gap, dan ejaan baku KBBI/EYD V."}
        </p>

        <div className="mt-5 grid gap-2 sm:grid-cols-2" role="group" aria-label="Cara memulai">
          {(
            [
              ["NEW", "Buat dari awal", "Belum punya judul. Agen membantu judul, rujukan, dan draf."],
              ["EXISTING", "Lanjutkan yang sudah ada", "Sudah punya judul, atau sudah menulis beberapa bab."],
            ] as Array<[StartMode, string, string]>
          ).map(([m, label, hint]) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              aria-pressed={mode === m}
              className={cn(
                "rounded-card border p-3 text-left transition-colors duration-200",
                mode === m ? "border-brand bg-sky-tint" : "border-hairline bg-white hover:bg-black/5"
              )}
            >
              <span className={cn("block text-[13.5px] font-semibold", mode === m ? "text-brand" : "text-black/85")}>{label}</span>
              <span className="mt-0.5 block text-[12px] text-black/55">{hint}</span>
            </button>
          ))}
        </div>

        <div className="mt-6 space-y-5">
          <div>
            <Label>Jurusan / bidang studi</Label>
            <div className="grid gap-2 sm:grid-cols-3">
              {DOMAINS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => set("domain", d)}
                  className={cn(
                    "rounded-card border p-3 text-left text-[13px] font-medium transition-colors duration-200",
                    form.domain === d
                      ? "border-brand bg-sky-tint text-brand"
                      : "border-hairline bg-white text-black/70 hover:bg-black/5"
                  )}
                >
                  {DOMAIN_LABEL[d]}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <Label htmlFor="method">Metode yang diinginkan</Label>
              <Select id="method" value={form.method} onChange={(e) => set("method", e.target.value as Method)}>
                {METHODS.map((m) => (
                  <option key={m} value={m}>{METHOD_LABEL[m]}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="degree">Jenjang</Label>
              <Select id="degree" value={form.degreeLevel} onChange={(e) => set("degreeLevel", e.target.value as DegreeLevel)}>
                <option value="S1">S1 (Sarjana)</option>
                <option value="S2">S2 (Magister)</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="template">Templat kampus</Label>
              <Select id="template" value={form.templateId} onChange={(e) => set("templateId", e.target.value)}>
                <optgroup label="Bawaan">
                  {templates.filter((t) => !t.is_custom).map((t) => (
                    <option key={t.campus_id} value={t.campus_id}>{t.campus_name}</option>
                  ))}
                </optgroup>
                {templates.some((t) => t.is_custom) && (
                  <optgroup label="Dari PDF pedoman saya">
                    {templates.filter((t) => t.is_custom).map((t) => (
                      <option key={t.campus_id} value={t.campus_id}>{t.campus_name}</option>
                    ))}
                  </optgroup>
                )}
              </Select>
            </div>
          </div>

          <div>
            <Label>Bahasa skripsi</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang}
                  type="button"
                  onClick={() => set("language", lang)}
                  aria-pressed={form.language === lang}
                  className={cn(
                    "rounded-card border p-3 text-left transition-colors duration-200",
                    form.language === lang
                      ? "border-brand bg-sky-tint text-brand"
                      : "border-hairline bg-white text-black/70 hover:bg-black/5"
                  )}
                >
                  <span className="block text-[13.5px] font-semibold">{LANGUAGE_LABEL[lang]}</span>
                  <span className="mt-0.5 block text-[12px] text-black/55">
                    {lang === "en"
                      ? "Judul, isi draf, pertanyaan sidang, dan ekspor DOCX dalam bahasa Inggris penuh."
                      : "Seluruh naskah dan ekspor dalam Bahasa Indonesia baku (EYD V)."}
                  </span>
                </button>
              ))}
            </div>
            <FieldHint>
              Pilihan ini berlaku untuk isi skripsi; tampilan aplikasi tetap Bahasa Indonesia. Judul bab/subbab bawaan
              ikut diterjemahkan saat memilih English.
            </FieldHint>
          </div>

          <div>
            <Label htmlFor="topic">{existing ? "Judul skripsi Anda" : "Topik utama (ide kasar)"}</Label>
            <Textarea
              id="topic"
              value={form.topic}
              onChange={(e) => set("topic", e.target.value)}
              placeholder={
                existing
                  ? "Tulis judul lengkap sesuai yang sudah disetujui atau Anda pakai"
                  : "Contoh: penggunaan media pembelajaran game edukatif dan motivasi belajar siswa SMP dalam pembelajaran matematika"
              }
              rows={existing ? 2 : 3}
            />
            <FieldHint>
              {form.topic.trim().length} karakter — minimal 15
              {existing ? ". Judul ini dikunci apa adanya; Anda tetap bisa meminta alternatif di Langkah 2." : " agar Planner Agent bekerja baik."}
            </FieldHint>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="ghost" size="sm" onClick={extractFromTitle} disabled={extracting || form.topic.trim().length < 15}>
              {extracting ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
              Ekstrak variabel dari {existing ? "judul" : "topik"}
            </Button>
            <span className="text-[12px] text-black/45">Mengisi variabel X, Y, subjek, jurusan, dan metode dari kalimat di atas.</span>
          </div>
          {extractMsg && <p className={cn("text-[12.5px]", extractMsg.kind === "error" ? "text-vermillion" : "text-graphite")}>{extractMsg.text}</p>}

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="x">Variabel X</Label>
              <Input id="x" value={form.variableX} onChange={(e) => set("variableX", e.target.value)} placeholder="Penggunaan media pembelajaran game edukatif" />
            </div>
            <div>
              <Label htmlFor="y">Variabel Y</Label>
              <Input id="y" value={form.variableY} onChange={(e) => set("variableY", e.target.value)} placeholder="Motivasi belajar siswa" />
            </div>
          </div>

          <div>
            <Label htmlFor="subject">Lokasi / subjek penelitian</Label>
            <div className="relative">
              <MapPin size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-black/35" />
              <Input
                id="subject"
                value={form.subject}
                onChange={(e) => set("subject", e.target.value)}
                className="pl-9"
                placeholder="Siswa SMP Zainul Falah, Tangerang"
              />
            </div>
          </div>

          {existing && (
            <div className="rounded-card border border-hairline p-4">
              <label className="flex min-h-10 cursor-pointer items-start gap-3">
                <input type="checkbox" role="switch" className="mt-1.5 h-4 w-4" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />
                <span>
                  <span className="block text-[14px] font-semibold">Mode lanjutan</span>
                  <span className="block text-[12.5px] leading-relaxed text-black/55">
                    Saya sudah menemukan topik, fenomena, research problem, teori, dan metode. Penulis akan mengambil dan mengembangkannya per bab, bukan menggantinya.
                  </span>
                </span>
              </label>
              {advanced && (
                <div className="mt-4 border-t border-hairline pt-4">
                  <BriefFields value={brief} onChange={setBrief} idPrefix="new-brief" />
                </div>
              )}
            </div>
          )}

          {existing && <DraftImport value={imported} onChange={setImported} />}

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button size="lg" disabled={!valid || busy} onClick={handleSubmit}>
              {busy && <Loader2 size={16} className="animate-spin" />}
              {existing ? "Lanjutkan dengan naskah ini" : "Kunci Formulir"} <ArrowRight size={16} />
            </Button>
            <ButtonLink variant="text" href="/proyek">
              Beranda wizard
            </ButtonLink>
          </div>
          {error && <p className="text-[13px] text-vermillion">{error}</p>}
        </div>
      </Card>

      <div className="space-y-4">
        <Card>
          <div className="flex items-start justify-between gap-2">
            <h2 className="t-heading-sm">Templat terpilih</h2>
            {selectedSummary?.is_custom && (
              <Button variant="text" size="sm" onClick={removeCustom} aria-label="Hapus templat ini">
                <Trash2 size={14} />
              </Button>
            )}
          </div>
          <p className="mt-1 text-[13px] text-graphite">
            {template?.campus_name ?? "Memuat…"} · {template?.degree_level}
            {selectedSummary?.is_custom && " · dari PDF"}
          </p>
          <dl className="mt-4 space-y-2 text-[13px]">
            <div className="flex justify-between gap-2 border-b border-dashed border-hairline pb-2">
              <dt className="text-black/50">Margin</dt>
              <dd className="text-right font-medium">
                {template?.page_setup.margins_cm.top}-{template?.page_setup.margins_cm.left}-
                {template?.page_setup.margins_cm.bottom}-{template?.page_setup.margins_cm.right} cm
              </dd>
            </div>
            <div className="flex justify-between gap-2 border-b border-dashed border-hairline pb-2">
              <dt className="text-black/50">Font</dt>
              <dd className="font-medium">
                {template?.page_setup.font_family} {template?.page_setup.font_size_pt}pt
              </dd>
            </div>
            <div className="flex justify-between gap-2 border-b border-dashed border-hairline pb-2">
              <dt className="text-black/50">Spasi</dt>
              <dd className="font-medium">{template?.page_setup.line_spacing}</dd>
            </div>
            <div className="flex justify-between gap-2 border-b border-dashed border-hairline pb-2">
              <dt className="text-black/50">Gaya sitasi</dt>
              <dd className="font-medium">{template?.citation_style.replace("_", " ")}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-black/50">Target kata</dt>
              <dd className="font-medium">{template ? totalTargetWords(template).toLocaleString("id-ID") : "-"} kata</dd>
            </div>
          </dl>
        </Card>

        <GuidelineUpload
          degree={form.degreeLevel}
          method={form.method}
          onSaved={async (id) => {
            await loadTemplates();
            setForm((f) => ({ ...f, templateId: id }));
          }}
        />
      </div>
    </div>
  );
}
