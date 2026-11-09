import { createElement } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { BarChart, LineChart, PieChart } from "@/components/charts/charts";
import type { ChartSeries, ChartSpec, DiagramEngine } from "@/lib/types";

export interface RasterImage {
  dataUrl: string;
  width: number;
  height: number;
}

export const MERMAID_PRESETS: Array<{ title: string; uml: boolean; code: string }> = [
  {
    title: "Kerangka berpikir",
    uml: false,
    code: `flowchart LR
    X["Variabel X<br/>(independen)"] -->|pengaruh| Y["Variabel Y<br/>(dependen)"]
    M["Moderator / kontrol"] -.-> Y
    T["Landasan teori"] --> X
    T --> Y
    Y --> H["Hipotesis penelitian"]`,
  },
  {
    title: "Alur metodologi",
    uml: false,
    code: `flowchart TD
    A[Identifikasi masalah] --> B[Studi pustaka]
    B --> C[Rumusan masalah & hipotesis]
    C --> D[Penyusunan instrumen]
    D --> E[Pengumpulan data]
    E --> F[Analisis data]
    F --> G{Hipotesis terdukung?}
    G -->|Ya| H[Simpulan]
    G -->|Tidak| I[Kajian ulang]
    I --> C`,
  },
  {
    title: "Use case",
    uml: true,
    code: `flowchart LR
    U((Mahasiswa)) --> UC1(Mengisi formulir inisiasi)
    U --> UC2(Memilih judul)
    U --> UC3(Menarik rujukan)
    U --> UC4(Membuat draf)
    U --> UC5(Mengekspor DOCX)
    D((Dosen Pembimbing)) --> UC6(Meninjau draf)
    UC4 -.->|include| UC3`,
  },
  {
    title: "Activity diagram",
    uml: true,
    code: `flowchart TD
    S([Mulai]) --> A[Pengguna mengisi formulir]
    A --> B[Sistem menyusun judul & celah riset]
    B --> C{Judul disetujui?}
    C -->|Tidak| B
    C -->|Ya| D[Tarik rujukan dari OpenAlex/Crossref]
    D --> E[Writer Agent menyusun draf]
    E --> F[Panel review]
    F --> G([Selesai])`,
  },
  {
    title: "Class diagram",
    uml: true,
    code: `classDiagram
    class Thesis {
      +String id
      +String title
      +String method
      +generateOutline()
    }
    class Section {
      +String code
      +String content
      +int targetWords
    }
    class Reference {
      +String doi
      +String title
      +int year
    }
    Thesis "1" --> "*" Section
    Section "*" --> "*" Reference : cites`,
  },
];


const PLANTUML_PRESETS: Array<{ title: string; uml: boolean; code: string }> = [
  {
    title: "Use case",
    uml: true,
    code: `@startuml
left to right direction
actor Mahasiswa
actor "Dosen Pembimbing" as Dosen
rectangle Sistem {
  Mahasiswa --> (Mengisi formulir inisiasi)
  Mahasiswa --> (Memilih judul)
  Mahasiswa --> (Menarik rujukan)
  Mahasiswa --> (Membuat draf)
  Dosen --> (Meninjau draf)
  (Membuat draf) .> (Menarik rujukan) : include
}
@enduml`,
  },
  {
    title: "Class diagram",
    uml: true,
    code: `@startuml
class Thesis {
  +id: String
  +title: String
  +method: String
  +generateOutline()
}
class Section {
  +code: String
  +content: String
  +targetWords: int
}
class Reference {
  +doi: String
  +title: String
  +year: int
}
Thesis "1" --> "*" Section
Section "*" --> "*" Reference : mengutip
@enduml`,
  },
  {
    title: "Sequence diagram",
    uml: true,
    code: `@startuml
actor Mahasiswa
participant "Antarmuka" as UI
participant "Backend" as API
participant "LLM" as LLM
Mahasiswa -> UI : Klik "Buat draf"
UI -> API : POST /sections/1.1/generate
API -> LLM : Prompt + bukti RAG
LLM --> API : Draf + sitasi
API --> UI : Draf tersimpan
UI --> Mahasiswa : Tampilkan draf
@enduml`,
  },
  {
    title: "Activity diagram",
    uml: true,
    code: `@startuml
start
:Isi formulir inisiasi;
:Pilih judul;
repeat
  :Tarik rujukan;
repeat while (Rujukan cukup?) is (tidak)
:Buat draf per subbab;
:Review multi-agent;
stop
@enduml`,
  },
  {
    title: "Kerangka berpikir",
    uml: false,
    code: `@startuml
left to right direction
rectangle "Landasan teori" as T
rectangle "Variabel X\\n(independen)" as X
rectangle "Variabel Y\\n(dependen)" as Y
rectangle "Hipotesis" as H
T --> X
T --> Y
X --> Y : pengaruh
Y --> H
@enduml`,
  },
];

export const DIAGRAM_PRESETS: Array<{ engine: DiagramEngine; title: string; uml: boolean; code: string }> = [
  ...MERMAID_PRESETS.map((p) => ({ ...p, engine: "mermaid" as const })),
  ...PLANTUML_PRESETS.map((p) => ({ ...p, engine: "plantuml" as const })),
];

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Gagal membaca gambar"));
    reader.readAsDataURL(blob);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Gambar tidak dapat dimuat"));
    img.src = src;
  });
}

/** Render Mermaid/PlantUML ke PNG lewat Kroki. Melempar Error berisi pesan dari Kroki bila sintaks salah. */
export async function renderDiagramPng(engine: DiagramEngine, code: string): Promise<RasterImage> {
  const res = await fetch(`https://kroki.io/${engine}/png`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ diagram_source: code }),
  });
  if (!res.ok) {
    const detail = (await res.text().catch(() => "")).trim().slice(0, 200);
    throw new Error(detail || `Kroki menjawab status ${res.status}`);
  }
  const dataUrl = await blobToDataUrl(await res.blob());
  const img = await loadImage(dataUrl);
  return { dataUrl, width: img.naturalWidth, height: img.naturalHeight };
}

function chartElement(spec: Pick<ChartSpec, "kind" | "series" | "xlabel" | "ylabel">) {
  const { kind, series, xlabel, ylabel } = spec;
  if (kind === "bar") return createElement(BarChart, { series, xlabel, ylabel });
  if (kind === "line") return createElement(LineChart, { series, xlabel, ylabel });
  return createElement(PieChart, { series });
}

/** Rasterisasi grafik SVG buatan sendiri menjadi PNG (skala 2x) agar bisa disisipkan ke DOCX. */
export async function chartToPng(spec: ChartSpec): Promise<RasterImage> {
  const host = document.createElement("div");
  const root = createRoot(host);
  flushSync(() => root.render(chartElement(spec)));
  const svg = host.querySelector("svg");
  if (!svg) {
    root.unmount();
    throw new Error("Grafik gagal dirender");
  }
  const [, , vw, vh] = (svg.getAttribute("viewBox") ?? "0 0 560 300").split(/\s+/).map(Number);
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  svg.setAttribute("width", String(vw));
  svg.setAttribute("height", String(vh));
  svg.setAttribute("font-family", "Arial, Helvetica, sans-serif");
  const markup = new XMLSerializer().serializeToString(svg);
  root.unmount();

  const scale = 2;
  const url = URL.createObjectURL(new Blob([markup], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = await loadImage(url);
    const canvas = document.createElement("canvas");
    canvas.width = vw * scale;
    canvas.height = vh * scale;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas tidak tersedia");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return { dataUrl: canvas.toDataURL("image/png"), width: vw, height: vh };
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Angka dari sel tabel ala Indonesia ("62,20", "1.234,5"); null untuk teks, penanda [DATA], atau "< 0,001". */
export function parseLocaleNumber(raw: string): number | null {
  const t = raw.trim();
  if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(t)) return Number(t.replace(/\./g, "").replace(",", "."));
  if (/^-?\d+([.,]\d+)?$/.test(t)) return Number(t.replace(",", "."));
  return null;
}

export function dataUrlToBytes(dataUrl: string): Uint8Array {
  const b64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export interface SeriesStats {
  n: number;
  mean: number;
  sd: number;
  min: number;
  max: number;
}

export function seriesStats(series: ChartSeries[]): SeriesStats | null {
  const v = series.map((s) => s.value).filter((x) => Number.isFinite(x));
  if (v.length === 0) return null;
  const mean = v.reduce((a, b) => a + b, 0) / v.length;
  const variance = v.length > 1 ? v.reduce((a, b) => a + (b - mean) ** 2, 0) / (v.length - 1) : 0;
  return { n: v.length, mean, sd: Math.sqrt(variance), min: Math.min(...v), max: Math.max(...v) };
}

/** Baca CSV dua kolom (label, nilai) dengan pemisah koma, titik koma, atau tab. Baris judul otomatis dilewati. */
export function parseSeriesCsv(text: string): ChartSeries[] {
  const rows: ChartSeries[] = [];
  // Titik koma/tab memberi ruang bagi koma desimal ala Excel Indonesia ("72,5").
  const delimiter = /[;\t]/.test(text) ? /[;\t]/ : /,/;
  for (const line of text.split(/\r?\n/)) {
    const cells = line.split(delimiter).map((c) => c.trim().replace(/^"|"$/g, ""));
    if (cells.length < 2 || !cells[0]) continue;
    const value = Number(cells[1].replace(",", "."));
    if (!Number.isFinite(value) || cells[1] === "") continue;
    rows.push({ label: cells[0], value });
  }
  return rows;
}
