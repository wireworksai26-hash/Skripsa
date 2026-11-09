import type { DiagramEngine, InisiasiForm } from "@/lib/types";
import { DIAGRAM_PRESETS } from "@/lib/visuals";

export interface DiagramPreset {
  engine: DiagramEngine;
  title: string;
  uml: boolean;
  code: string;
  /** Bab tujuan bawaan: kerangka konseptual di Bab II, prosedur & analisis di Bab III. */
  chapter: string;
}

/** Label aman untuk simpul Mermaid: tanpa tanda kutip/kurung siku yang merusak sintaks. */
const label = (s: string, fallback: string) => (s || fallback).replace(/["[\]{}<>|]/g, "").replace(/\s+/g, " ").trim().slice(0, 70);

/**
 * Preset diagram yang mengikuti metode, bahasa, dan variabel proyek (audit BUG-04: sebelumnya selalu kerangka
 * kuantitatif X→Y→hipotesis berbahasa Indonesia, apa pun metodenya).
 */
export function diagramPresets(form: Pick<InisiasiForm, "method" | "language" | "variableX" | "variableY" | "subject" | "domain">): DiagramPreset[] {
  const en = form.language === "en";
  const x = label(form.variableX, en ? "Focus 1" : "Fokus 1");
  const y = label(form.variableY, en ? "Focus 2" : "Fokus 2");
  const ctx = label(form.subject, en ? "Research context" : "Konteks penelitian");
  const T = (id: string, eng: string) => (en ? eng : id);
  const out: DiagramPreset[] = [];

  if (form.method === "KUALITATIF") {
    out.push(
      {
        engine: "mermaid",
        uml: false,
        chapter: "2",
        title: T("Kerangka konseptual", "Conceptual framework"),
        code: `flowchart TD
    A["${ctx}"] --> B["${x}"]
    B --> C["${y}"]
    B --> D["${T("Pengalaman dan persepsi partisipan", "Participants' experiences and perceptions")}"]
    C --> D
    D --> E["${T("Dimensi afektif", "Affective dimension")}"]
    D --> F["${T("Dimensi kognitif dan kebahasaan", "Cognitive and linguistic dimension")}"]
    E --> G["${T("Temuan yang menjawab rumusan masalah", "Findings answering the research questions")}"]
    F --> G`,
      },
      {
        engine: "mermaid",
        uml: false,
        chapter: "3",
        title: T("Model analisis data interaktif (Miles, Huberman & Saldaña)", "Interactive data analysis model (Miles, Huberman & Saldaña)"),
        code: `flowchart LR
    A["${T("Pengumpulan data", "Data collection")}"] --> B["${T("Kondensasi data", "Data condensation")}"]
    A --> C["${T("Penyajian data", "Data display")}"]
    B <--> C
    B <--> D["${T("Penarikan dan verifikasi kesimpulan", "Conclusion drawing and verification")}"]
    C <--> D
    A <--> D`,
      },
      {
        engine: "mermaid",
        uml: false,
        chapter: "3",
        title: T("Prosedur penelitian", "Research procedure"),
        code: `flowchart TD
    A["${T("Studi pendahuluan dan perizinan", "Preliminary study and permission")}"] --> B["${T("Penyusunan instrumen (pedoman wawancara, observasi)", "Instrument development (interview guide, observation)")}"]
    B --> C["${T("Pengumpulan data di", "Data collection at")} ${ctx}"]
    C --> D["${T("Analisis data tematik", "Thematic data analysis")}"]
    D --> E["${T("Uji keabsahan: triangulasi dan member checking", "Trustworthiness: triangulation and member checking")}"]
    E --> F["${T("Penulisan laporan", "Report writing")}"]`,
      }
    );
  } else if (form.method === "RND") {
    out.push({
      engine: "mermaid",
      uml: false,
      chapter: "3",
      title: T("Prosedur pengembangan (ADDIE)", "Development procedure (ADDIE)"),
      code: `flowchart LR
    A["${T("Analisis", "Analysis")}"] --> B["${T("Desain", "Design")}"] --> C["${T("Pengembangan", "Development")}"] --> D["${T("Implementasi", "Implementation")}"] --> E["${T("Evaluasi", "Evaluation")}"]
    E -. ${T("revisi", "revision")} .-> B`,
    });
  } else {
    out.push(
      {
        engine: "mermaid",
        uml: false,
        chapter: "2",
        title: T("Kerangka berpikir", "Conceptual framework"),
        code: `flowchart LR
    T["${T("Landasan teori", "Theoretical framework")}"] --> X["${x}"]
    T --> Y["${y}"]
    X -->|${T("pengaruh", "effect")}| Y
    Y --> H["${T("Hipotesis penelitian", "Research hypothesis")}"]`,
      },
      {
        engine: "mermaid",
        uml: false,
        chapter: "3",
        title: T("Alur penelitian", "Research flow"),
        code: `flowchart TD
    A["${T("Identifikasi masalah", "Problem identification")}"] --> B["${T("Kajian pustaka", "Literature review")}"]
    B --> C["${T("Rumusan masalah dan hipotesis", "Research questions and hypotheses")}"]
    C --> D["${T("Penyusunan dan uji instrumen", "Instrument development and testing")}"]
    D --> E["${T("Pengumpulan data", "Data collection")}"]
    E --> F["${T("Analisis statistik", "Statistical analysis")}"]
    F --> G["${T("Simpulan", "Conclusion")}"]`,
      }
    );
  }

  // Diagram UML untuk Informatika (Bab III: analisis & perancangan sistem).
  if (form.domain === "INFORMATIKA") {
    for (const p of DIAGRAM_PRESETS.filter((d) => d.uml)) out.push({ ...p, chapter: "3" });
  }
  return out;
}
