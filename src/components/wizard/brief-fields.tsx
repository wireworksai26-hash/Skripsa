"use client";

import { FieldHint, Label, Textarea } from "@/components/ui/field";
import type { Brief } from "@/lib/types";

export const EMPTY_BRIEF: Brief = { topic: "", phenomenon: "", problem: "", theory: "", method: "" };

const FIELDS: Array<{ key: keyof Brief; label: string; placeholder: string; hint: string }> = [
  { key: "topic", label: "Topik", placeholder: "Mis. Student-led presentation dalam pembelajaran bahasa Inggris", hint: "Dipakai di Bab I dan II." },
  { key: "phenomenon", label: "Fenomena", placeholder: "Mis. Mahasiswa mengandalkan AI untuk menyusun slide dan naskah presentasi", hint: "Menjadi dasar Latar Belakang (Bab I)." },
  { key: "problem", label: "Research problem", placeholder: "Mis. Belum jelas bagaimana ketergantungan pada AI memengaruhi keterlibatan siswa saat presentasi", hint: "Dipakai di Bab I, II, IV, dan V." },
  { key: "theory", label: "Teori", placeholder: "Mis. Self-Determination Theory (Deci & Ryan) dan konsep engagement", hint: "Dipakai di Bab II; Bab IV dan V mengaitkan temuan ke teori ini. Bila menulis rujukan, satu per baris: Penulis, A. (tahun). Judul. Di Langkah 3 baris itu dicocokkan otomatis ke basis data." },
  { key: "method", label: "Metode", placeholder: "Mis. Studi kasus kualitatif; wawancara semi-terstruktur dan observasi; analisis tematik", hint: "Desain, pengumpulan data, dan analisis. Dipakai di Bab III." },
];

/** Kerangka yang sudah ditemukan peneliti: agen mengembangkannya, bukan menggantinya. */
export function BriefFields({ value, onChange, idPrefix = "brief" }: { value: Brief; onChange: (b: Brief) => void; idPrefix?: string }) {
  return (
    <div className="grid gap-4">
      {FIELDS.map((f) => (
        <div key={f.key}>
          <Label htmlFor={`${idPrefix}-${f.key}`}>{f.label}</Label>
          <Textarea id={`${idPrefix}-${f.key}`} rows={f.key === "theory" ? 5 : 2} maxLength={1500} value={value[f.key]} onChange={(e) => onChange({ ...value, [f.key]: e.target.value })} placeholder={f.placeholder} />
          <FieldHint>{f.hint}</FieldHint>
        </div>
      ))}
    </div>
  );
}

export const briefFilled = (b: Brief) => Object.values(b).some((v) => v.trim().length > 0);
