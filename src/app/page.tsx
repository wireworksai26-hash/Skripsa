import {
  ArrowDown,
  Bot,
  FileText,
  SearchCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { InstallButton } from "@/components/pwa/install-button";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { ProductPreview } from "@/components/landing/product-preview";
import { ResearchTabs } from "@/components/landing/research-tabs";
import { ThemeButton } from "@/components/pwa/theme-toggle";

const NAV_ANCHORS = [
  { href: "#fitur", label: "Fitur" },
  { href: "#alur", label: "Alur kerja" },
  { href: "#agen", label: "Agen" },
  { href: "#desain-penelitian", label: "Desain penelitian" },
];

const SPLIT_FEATURES = [
  {
    eyebrow: "Rujukan",
    heading: "Rujukan asli, bukan karangan.",
    body: "Setiap artikel ditarik langsung dari OpenAlex, Crossref, DOAJ, dan ERIC — dengan DOI aktif yang bisa diuji dosen pembimbing kapan pun.",
  },
  {
    eyebrow: "Editor",
    heading: "Draf per subbab, tersinkron.",
    body: "Outline lima bab digenerate dari template kampus, lalu tiap subbab ditulis terpisah dengan target jumlah kata — semuanya sejak awal berada dalam satu sistem.",
  },
  {
    eyebrow: "Grounding",
    heading: "Sitasi lengkap dengan cuplikan aslinya.",
    body: "Setiap sitasi dalam-teks menautkan kalimat asli dari abstrak artikel, distabilo dan siap diperiksa dosen tanpa buka-buka PDF.",
  },
];

const AGENTS_BAND = [
  {
    name: "Advisor Agent",
    role: "Dosen Pembimbing",
    color: "#ffb110",
    body: "Menjaga urgensi latar belakang dan mempertajam kebaruan ilmiah.",
  },
  {
    name: "Examiner Agent",
    role: "Dosen Penguji",
    color: "#f64932",
    body: "Menyusun dugaan pertanyaan sidang beserta saran jawabannya.",
  },
  {
    name: "Academic Writer",
    role: "Penulis Akademik",
    color: "#62aef0",
    body: "Menulis draf per subbab dari konteks RAG, bahasa baku EYD V.",
  },
  {
    name: "Quality Guardrail",
    role: "Validator Kualitas",
    color: "#cbcbef",
    body: "Mengukur target kata dan mem-verify semua DOI aktif di Crossref.",
  },
];

function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-canvas/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center px-4">
        <a href="#" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-btn bg-brand text-white">
            <FileText size={17} />
          </span>
          <span className="text-[17px] font-bold tracking-tight">SkripsiAI</span>
        </a>
        <nav className="ml-8 hidden items-center gap-1 lg:flex">
          {NAV_ANCHORS.map((a) => (
            <a
              key={a.href}
              href={a.href}
              className="rounded-btn px-3 py-1.5 text-[14px] text-black/80 transition-colors hover:bg-black/5"
            >
              {a.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <InstallButton quiet />
          <ThemeButton />
          <ButtonLink variant="primary" href="/proyek">
            Mulai Proyek
          </ButtonLink>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-4 pt-20">
      <div className="mx-auto max-w-3xl text-center">
        <Pill tone="sky">
          <Sparkles size={12} /> Multi-agent thesis drafting · PWA
        </Pill>
        <h1 className="t-display mt-6">
          Mahasiswa, agen, dan dosen{" "}
          <span className="rounded-card bg-marigold/30 px-3 text-ink dark:bg-[#fbbf24]/15 dark:text-[#fbbf24]">berpikir bersama.</span>
        </h1>
        <p className="t-serif-lede mx-auto mt-6 max-w-xl text-graphite">
          Isi satu formulir, tarik rujukan nyata, dan pulang dengan draf lima bab bersitasi lengkap.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <ButtonLink variant="primary" size="lg" href="/proyek/1-inisiasi">
            <Sparkles size={16} /> Mulai sekarang
          </ButtonLink>
          <ButtonLink variant="text" size="lg" href="#fitur">
            Lihat cara kerja <ArrowDown size={15} />
          </ButtonLink>
        </div>
        <p className="mt-4 text-[13px] text-black/60">
          Tanpa prompt menulis · proyek tersimpan di akun Anda
        </p>
      </div>
      <ProductPreview />

    </section>
  );
}

const SOURCES_MONO = ["OpenAlex", "Crossref", "DOAJ", "ERIC", "CORE", "arXiv"];
const STATS = [
  { value: "6", label: "basis data jurnal terbuka" },
  { value: "4", label: "agen penilai dan penulis" },
  { value: "6", label: "langkah dari formulir ke DOCX" },
  { value: "3", label: "templat nasional + PDF pedoman kampus Anda" },
];

function LogoWall() {
  return (
    <section className="mx-auto max-w-6xl px-4 pt-20 pb-2">
      <p className="text-center text-[13px] font-medium uppercase tracking-widest text-black/55">
        Menarik rujukan dari basis data terbuka yang sama
      </p>
      <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4" aria-label="Sumber rujukan">
        {SOURCES_MONO.map((name) => (
          <li key={name} className="text-[18px] font-bold tracking-tight text-black/40 grayscale transition-colors hover:text-black/70">
            {name}
          </li>
        ))}
      </ul>
      <dl className="mx-auto mt-12 grid max-w-4xl grid-cols-2 gap-6 border-y border-hairline py-8 md:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.label} className="text-center">
            <dt className="t-heading text-brand">{s.value}</dt>
            <dd className="mt-1 text-[13px] leading-snug text-black/65">{s.label}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function SplitFeatures() {
  return (
    <section id="fitur" className="mx-auto max-w-6xl px-4 pt-24">
      <div className="grid gap-4 md:grid-cols-3">
        {SPLIT_FEATURES.map((f) => (
          <Card key={f.heading} className="flex flex-col">
            <p className="text-[12px] font-semibold uppercase tracking-widest text-brand">
              {f.eyebrow}
            </p>
            <h2 className="t-heading-sm mt-3">{f.heading}</h2>
            <p className="mt-3 text-[14.5px] leading-relaxed text-graphite">{f.body}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

function PipelineRow() {
  const FLOW = [
    { n: 1, label: "Isi Formulir", detail: "Promptless input" },
    { n: 2, label: "Pilih Judul", detail: "5 opsi + gap" },
    { n: 3, label: "Tarik Rujukan", detail: "API publik gratis" },
    { n: 4, label: "Draf Subbab", detail: "Split-screen" },
    { n: 5, label: "Visual Data", detail: "Grafik & diagram" },
    { n: 6, label: "Review & Ekspor", detail: "DOCX presisi" },
  ];
  return (
    <section id="alur" className="mx-auto max-w-6xl px-4 pt-16">
      <h2 className="t-heading">Alur pipeline multi-agent</h2>
      <p className="t-serif-lede mt-3 max-w-xl text-graphite">
        Tiap agen menyimpan konteks ke state manager — hasil kerja satu agen
        menjadi masukan utama bagi agen berikutnya.
      </p>
      <div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {FLOW.map((s) => (
          <Card key={s.n} className="p-4">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-midnight text-[12px] font-bold text-white">
              {s.n}
            </span>
            <p className="mt-3 text-[14px] font-semibold">{s.label}</p>
            <p className="text-[12px] text-black/50">{s.detail}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

function AgentsBand() {
  return (
    <section id="agen" className="mt-24 bg-[#0d0d12] py-20 text-white">
      <div className="mx-auto max-w-6xl px-4">
        <div className="max-w-2xl">
          <p className="text-[12px] font-semibold uppercase tracking-widest text-[#9a9cc0]">
            Empat agen
          </p>
          <h2 className="t-heading-lg mt-3">
            Empat agen mengawal draf Anda dari ide ke DOCX.
          </h2>
          <p className="t-serif-lede mt-4 text-white/70">
            Tugas ringan seperti judul dijalankan di model cepat, sedangkan draf subbab panjang
            memakai model besar; bila satu penyedia gagal, pekerjaan pindah otomatis ke yang lain.
          </p>
        </div>
        <div className="mt-10 grid gap-3 md:grid-cols-2">
          {AGENTS_BAND.map((a) => (
            <div
              key={a.name}
              className="rounded-card border border-white/10 bg-white/[0.04] p-5 transition-colors hover:bg-white/[0.07]"
            >
              <div className="flex items-center gap-3">
                <span
                  className="grid h-10 w-10 place-items-center rounded-full"
                  style={{ background: `${a.color}22`, color: a.color }}
                >
                  <Bot size={18} />
                </span>
                <div>
                  <p className="font-semibold">{a.name}</p>
                  <p className="text-[12px] text-white/55">{a.role}</p>
                </div>
              </div>
              <p className="mt-3 text-[14.5px] leading-relaxed text-white/75">
                {a.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function UseCaseCards() {
  return (
    <section id="desain-penelitian" className="mx-auto max-w-6xl px-4 pt-24">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="t-heading-lg">Dibangun untuk semua desain penelitian.</h2>
          <p className="t-serif-lede mt-3 max-w-xl text-graphite">
            Template kampus menyeraraskan heading, margin, target kata, dan gaya
            sitasi menurut metode serta jenjang studi Anda.
          </p>
        </div>
        <ButtonLink variant="ghost" href="/proyek/1-inisiasi">
          Pilih desain →
        </ButtonLink>
      </div>
      <ResearchTabs />
    </section>
  );
}

function FinalCta() {
  return (
    <section className="mx-auto max-w-6xl px-4 pt-24 pb-24">
      <div className="flex flex-col items-center gap-5 rounded-card border border-hairline bg-white py-14 text-center">
        <Pill tone="blue">
          <SearchCheck size={12} /> Mulai dari formulir
        </Pill>
        <h2 className="t-heading-lg max-w-2xl">
          Bawa ide kasar, pulang membawa draf lima bab.
        </h2>
        <ButtonLink variant="primary" size="lg" href="/proyek/1-inisiasi">
          Isi formulir inisiasi →
        </ButtonLink>
        <p className="flex max-w-lg items-start gap-2 text-left text-[12px] text-black/45">
          <TriangleAlert size={13} className="mt-0.5 shrink-0" />
          Disclaimer: draf berfungsi sebagai bahan bimbingan awal — bukan jasa
          joki skripsi. Selalu tulis ulang dengan pemikiran kritis Anda sendiri.
        </p>
      </div>
    </section>
  );
}

function SiteFooter() {
  const columns = [
    {
      title: "Produk",
      links: [
        { label: "Fitur unggulan", href: "#fitur" },
        { label: "Alur kerja pipa", href: "#alur" },
        { label: "Agen AI", href: "#agen" },
        { label: "Mulai proyek", href: "/proyek" },
      ],
    },
    {
      title: "Sumber data",
      links: [
        { label: "OpenAlex", href: "https://openalex.org" },
        { label: "Crossref", href: "https://www.crossref.org" },
        { label: "DOAJ", href: "https://doaj.org" },
        { label: "ERIC", href: "https://eric.ed.gov" },
      ],
    },
    {
      title: "Standar ilmiah",
      links: [
        { label: "APA 7th", href: "#fitur" },
        { label: "EYD V", href: "#fitur" },
      ],
    },
  ];
  return (
    <footer className="border-t border-hairline bg-white">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-[2fr_1fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-btn bg-brand text-white">
              <FileText size={17} />
            </span>
            <span className="text-[17px] font-bold tracking-tight">SkripsiAI</span>
          </div>
          <p className="t-serif-lede mt-3 max-w-xs text-[14px] text-graphite">
            Draf skripsi bersitasi terverifikasi, disusun berurutan oleh tim agen
            untuk mahasiswa S1/S2.
          </p>
        </div>
        {columns.map((col) => (
          <div key={col.title}>
            <p className="text-[13px] font-semibold">{col.title}</p>
            <ul className="mt-3 space-y-2">
              {col.links.map((l) => (
                <li key={l.label}>
                  <a
                    href={l.href}
                    className="text-[13px] text-black/60 hover:text-black"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-hairline">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-5 text-[12px] text-black/45">
          <span>© 2026 SkripsiAI · Multi-Agent Thesis Drafting PWA</span>
          <span>OpenAlex · Crossref · DOAJ · ERIC · arXiv</span>
        </div>
      </div>
    </footer>
  );
}

export default function HomePage() {
  return (
    <div className="overflow-x-hidden">
      <SiteHeader />
      <main>
        <Hero />
        <LogoWall />
        <SplitFeatures />
        <PipelineRow />
        <AgentsBand />
        <UseCaseCards />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  );
}
