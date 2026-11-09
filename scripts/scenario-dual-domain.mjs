#!/usr/bin/env node
/**
 * Skenario uji dua jurusan terhadap backend yang sedang berjalan (Fase 4: pengujian dual-domain).
 *
 *   node scripts/scenario-dual-domain.mjs            # memakai http://localhost:8000
 *   API_URL=http://server:8000 node scripts/scenario-dual-domain.mjs
 *
 * Setiap jurusan menjalankan alur nyata: judul -> rujukan -> draf -> uji statistik -> review. Memanggil LLM dan
 * API ilmiah sungguhan, jadi butuh kunci di backend/.env dan internet. Proyek uji dihapus di akhir; akun uji
 * (…@skenario-uji.id) tetap ada karena belum ada endpoint hapus akun.
 */
const API = (process.env.API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const SCENARIOS = [
  {
    name: "Informatika (kuantitatif)",
    domain: "INFORMATIKA",
    method: "KUANTITATIF",
    topic: "Pengaruh sistem rekomendasi berbasis machine learning terhadap hasil belajar mahasiswa",
    x: "Sistem rekomendasi materi berbasis machine learning",
    y: "Hasil belajar mahasiswa",
    subject: "Mahasiswa Teknik Informatika semester lima",
    query: "machine learning recommendation system students learning outcomes",
    expectSource: "arXiv",
    sections: ["1.1", "3.1"],
    groups: [
      { name: "Kontrol", values: [62, 65, 61, 64, 63, 66, 60, 62] },
      { name: "Eksperimen", values: [74, 78, 72, 80, 77, 75, 79, 76] },
    ],
  },
  {
    name: "Pendidikan Bahasa Inggris (kualitatif)",
    domain: "ENGLISH_EDUCATION",
    method: "KUALITATIF",
    topic: "Students perceptions of task-based language teaching in speaking classes at junior high school",
    x: "Task-based language teaching",
    y: "Students perceptions of speaking class",
    subject: "Eighth grade students at a junior high school in Bandung",
    query: "task-based language teaching speaking perceptions junior high school",
    expectSource: "ERIC",
    sections: ["1.1", "2.1"],
    groups: [
      { name: "Pre", values: [55, 60, 58, 62, 57, 59] },
      { name: "Post", values: [66, 70, 65, 72, 68, 69] },
    ],
  },
];

async function call(path, { body, token, method } = {}) {
  const res = await fetch(API + path, {
    method: method ?? (body ? "POST" : "GET"),
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method ?? (body ? "POST" : "GET")} ${path} -> ${res.status} ${text.slice(0, 200)}`);
  return text ? JSON.parse(text) : null;
}

const results = [];
function check(scenario, label, ok, detail = "") {
  results.push({ scenario, label, ok });
  console.log(`  ${ok ? "LULUS" : "GAGAL"}  ${label}${detail ? ` — ${detail}` : ""}`);
}

async function run(sc) {
  console.log(`\n== ${sc.name}`);
  const t0 = Date.now();
  const reg = await call("/auth/register", {
    body: { full_name: `Uji ${sc.domain}`, email: `${sc.domain.toLowerCase()}-${Date.now()}@skenario-uji.id`, password: "rahasia123", major_name: sc.name, campus_name: "Kampus Uji" },
  });
  const token = reg.access_token;
  let thesisId;
  try {
    const th = await call("/theses", { token, body: { topic: sc.topic, variable_x: sc.x, variable_y: sc.y, subject: sc.subject, method: sc.method, domain: sc.domain, degree_level: "S1" } });
    thesisId = th.thesis_id;
    check(sc.name, "templat mengikuti metode", sc.method === "KUALITATIF" ? th.campus_template_id === "nasional-s1-kualitatif" : th.campus_template_id === "nasional-s1-kuantitatif", th.campus_template_name);

    const titles = await call(`/theses/${thesisId}/titles`, { token, body: {} });
    check(sc.name, "5 judul dari LLM", titles.titles.length >= 3 && !!titles.provider, `${titles.titles.length} judul oleh ${titles.provider}`);

    const found = await call("/references/search", { token, body: { query: `${sc.topic} ${sc.query}`, domain: sc.domain } });
    const bySource = {};
    for (const r of found.refs) bySource[r.source_database] = (bySource[r.source_database] ?? 0) + 1;
    check(sc.name, "rujukan terkumpul", found.refs.length >= 8, `${found.refs.length} rujukan ${JSON.stringify(bySource)}`);
    check(sc.name, `sumber khusus bidang (${sc.expectSource}) ikut tampil`, (bySource[sc.expectSource] ?? 0) > 0);
    check(sc.name, "tidak ada sumber gagal", found.errors.length === 0, found.errors.join(", "));
    check(sc.name, "ada rujukan dengan tautan PDF", found.refs.some((r) => r.pdf_url));

    const saved = await call(`/theses/${thesisId}/citations`, { token, body: found.refs });
    const ids = saved.slice(0, 6).map((c) => c.citation_id);
    await call(`/theses/${thesisId}`, { token, method: "PATCH", body: { selected_ref_ids: ids, picked_title_id: titles.titles[0].title_id, title: titles.titles[0].text } });
    await call(`/theses/${thesisId}/sections/build`, { token, body: {} });

    for (const code of sc.sections) {
      const g = await call(`/theses/${thesisId}/sections/${code}/generate`, { token, body: {} });
      const textOk = g.citations_json.length > 0 && g.citations_json.every((c) => g.content_markdown.includes(c.marker));
      check(sc.name, `draf ${code}: sitasi tertulis di teks`, textOk, `${g.word_count} kata, ${g.citations_json.length} sitasi, oleh ${g.provider}`);
      const abstracts = new Map(saved.map((c) => [c.citation_id, (c.highlighted_snippet ?? "").toLowerCase().replace(/[^a-z0-9]+/g, " ")]));
      const grounded = g.citations_json.every((c) => {
        const abs = abstracts.get(c.reference_id) ?? "";
        const snip = c.snippet.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
        return abs === "" || abs.includes(snip) || c.snippet.startsWith("Cuplikan abstrak tidak tersedia");
      });
      check(sc.name, `draf ${code}: snippet stabilo kutipan nyata dari abstrak`, grounded);
    }

    const stats = await call("/stats/analyze", { token, body: { groups: sc.groups, paired: sc.groups[0].name === "Pre" } });
    check(sc.name, "uji statistik", !!stats.test && stats.interpretation.length > 40, stats.test?.report ?? "");
    await call(`/theses/${thesisId}/tables`, { token, body: { title: "Statistik deskriptif", columns: ["Kelompok", "n"], rows: stats.descriptives.map((d) => [d.group, String(d.n)]) } });

    const review = await call(`/theses/${thesisId}/review`, { token, body: {} });
    const ex = review.reviews.EXAMINER;
    check(sc.name, "Examiner Agent (LLM) menyusun pertanyaan sidang", ex.done && ex.notes.length >= 5, `${ex.notes.length} pertanyaan`);
    check(sc.name, "Advisor dan Guardrail selesai", review.reviews.ADVISOR.done && review.reviews.GUARDRAIL.done);
    for (const k of ["GUARDRAIL", "ADVISOR"]) {
      const v = review.reviews[k];
      console.log(`  ${k} skor ${v.score}${v.cap ? ` (batas ${v.cap})` : ""}: ` + (v.breakdown || []).map((b) => `${b.key} ${b.points}/${b.max}`).join(" · "));
    }

    const full = await call(`/theses/${thesisId}`, { token });
    check(sc.name, "data tersimpan di server (rehidrasi)", full.sections.some((s) => s.word_count > 0) && full.tables.length === 1 && Object.keys(full.review_json).length === 3);
  } finally {
    if (thesisId) await call(`/theses/${thesisId}`, { token, method: "DELETE" }).catch(() => {});
  }
  console.log(`  (selesai ${((Date.now() - t0) / 1000).toFixed(0)} detik)`);
}

const health = await call("/health").catch((e) => {
  console.error(`Backend tidak terjangkau di ${API}: ${e.message}`);
  process.exit(2);
});
console.log(`Backend ${API} · LLM: ${JSON.stringify(health.llm?.routing)} · Unpaywall: ${health.unpaywall}`);

for (const sc of SCENARIOS) {
  try {
    await run(sc);
  } catch (e) {
    check(sc.name, "skenario berjalan sampai selesai", false, e.message);
  }
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} pemeriksaan lulus${failed.length ? `; gagal: ${failed.map((f) => `${f.scenario} › ${f.label}`).join(" | ")}` : ""}`);
process.exit(failed.length ? 1 : 0);
