import { FileText, Quote } from "lucide-react";

/** Ilustrasi tampilan split-screen: draf dengan penanda sitasi di kiri, kalimat asli abstrak yang disorot di kanan. Teks contoh, bukan data nyata. */
export function ProductPreview() {
  return (
    <figure className="mx-auto mt-14 max-w-5xl">
      <div className="overflow-hidden rounded-card border border-hairline-strong bg-white shadow-[0_24px_60px_-28px_rgba(0,0,0,0.35)]">
        <div className="flex items-center gap-1.5 border-b border-hairline px-4 py-2.5" aria-hidden>
          <span className="h-2.5 w-2.5 rounded-full bg-coral/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-marigold/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#4cc15f]/80" />
          <span className="ml-3 truncate text-[12px] text-black/45">Langkah 4 · Draf · 1.1 Latar Belakang Masalah</span>
        </div>
        <div className="grid md:grid-cols-2">
          <div className="p-5 text-left sm:p-6">
            <p className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-widest text-black/45">
              <FileText size={13} /> Draf subbab
            </p>
            <p className="mt-3 text-[14.5px] leading-[1.75] text-charcoal">
              Media digital yang dirancang interaktif terbukti meningkatkan keterlibatan siswa dalam pembelajaran sains{" "}
              <span className="rounded-[4px] bg-brand/10 px-1 font-medium text-brand underline decoration-brand/40 underline-offset-2">(Nur &amp; Dewi, 2021)</span>.
              Namun, belum banyak kajian yang menguji hubungan tersebut pada kelas dengan akses perangkat terbatas.
            </p>
            <div className="mt-4 h-2 w-2/3 rounded-pill bg-black/8" />
            <div className="mt-2 h-2 w-1/2 rounded-pill bg-black/8" />
          </div>
          <div className="border-t border-hairline bg-canvas p-5 text-left sm:p-6 md:border-l md:border-t-0">
            <p className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-widest text-black/45">
              <Quote size={13} /> Abstrak artikel asli
            </p>
            <p className="mt-3 text-[13.5px] leading-[1.75] text-black/70">
              This study examines interactive digital media in secondary science classrooms.{" "}
              <mark className="rounded-[3px] bg-marigold/45 px-0.5 text-inherit">Interactive digital media significantly increased student engagement across 12 schools.</mark>{" "}
              Limitations and implications are discussed.
            </p>
            <p className="mt-3 text-[12px] text-black/50">Klik penanda sitasi, PDF terbuka dan kalimat yang dikutip langsung tersorot.</p>
          </div>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-[12px] text-black/50">Ilustrasi tampilan; isi hanyalah contoh.</figcaption>
    </figure>
  );
}
