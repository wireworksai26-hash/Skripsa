# SkripsiAI

Generator skripsi multi-agent berbentuk PWA. Mahasiswa mengisi satu formulir, memilih judul, menarik rujukan jurnal nyata, lalu agen menulis draf per subbab dengan sitasi yang bisa diperiksa. Hasilnya diekspor ke `.docx` sesuai format kampus.

> Draf adalah bahan bimbingan awal, bukan jasa joki. Tulis ulang dengan pemikiran Anda sendiri dan konsultasikan dengan dosen pembimbing.

## Fitur utama

- **Alur 6 langkah**: Inisiasi, Judul, Rujukan, Draf, Visual & Data, Review & Ekspor.
- **Rujukan nyata** dari OpenAlex, Crossref, DOAJ, ERIC, CORE, dan arXiv (Unpaywall dan Semantic Scholar bila dikonfigurasi). DOI diverifikasi ke Crossref; kutipan stabilo selalu kalimat asli dari abstrak.
- **Templat kampus**: templat nasional (kuantitatif, kualitatif, analisis dokumen, R&D, PTK, studi pustaka, S2) atau unggah PDF pedoman kampus untuk diekstrak otomatis. Struktur bab bisa disunting per proyek, termasuk subbab tingkat 3 (2.1.1).
- **Dua bahasa naskah**: Indonesia dan Inggris, lengkap dengan judul bab dan subbab.
- **Data penelitian sendiri untuk Bab IV**: angka diolah deterministik, teks wawancara/observasi dikodekan agen menjadi tema dengan kutipan yang diverifikasi persis.
- **Tabel, grafik, dan diagram** per bab, termasuk saran AI menurut jenis penelitian.
- **Panel review kritis**: Guardrail deterministik (duplikasi, kelengkapan, rujukan, kejujuran data) dan Advisor berbasis rubrik dengan batas skor. Plus simulasi pertanyaan sidang dan latihan menjawab.
- **Halaman depan lengkap**: sampul dengan logo, halaman judul, persetujuan, pernyataan keaslian, abstrak ID/EN, kata pengantar, daftar isi/tabel/gambar/grafik, dan lampiran instrumen.
- **Kolaborasi**: tautan baca-saja untuk dosen pembimbing dengan komentar per subbab.
- **Utilitas**: impor/ekspor BibTeX dan RIS, cek kemiripan terhadap rujukan, riwayat versi dengan diff, target menulis harian dan streak.
- **PWA**: bisa dipasang, mode gelap, antrean suntingan saat offline, dan push notification (OneSignal).
- Ekspor `.docx` bisa dilakukan kapan saja, termasuk saat naskah baru sampai Bab III.

## Prinsip

Tidak ada data karangan. Bila LLM atau sumber gagal, aplikasi menampilkan galat yang jelas, bukan teks pengganti. Sitasi dibangun dari metadata rujukan, angka yang tidak ada di draf ditolak, dan tempat data yang belum ada diberi penanda `[DATA: …]`.

## Arsitektur

| Bagian | Teknologi |
|---|---|
| Frontend | Next.js 15 (App Router), React 19, Tailwind CSS v4, zustand, `docx`, `pdfjs-dist` |
| Backend | FastAPI, SQLAlchemy (SQLite), Pydantic |
| LLM | NVIDIA NIM (tugas berat) dengan cadangan Groq dan Gemini (tugas cepat), pindah otomatis bila gagal |
| Diagram | Kroki (Mermaid/PlantUML) |

```
src/                  frontend (app/, components/, lib/)
backend/app/          API (routers/, services/, services/agents/, models/)
backend/tests/        pytest
scripts/              skrip pendukung (ikon, skenario uji)
docs/                 PRD, audit, rencana uji beta
public/               manifest, service worker, ikon, halaman offline
```

## Menjalankan secara lokal

Prasyarat: Node.js 20+ dan Python 3.11+.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows;  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # isi kunci API, lihat bagian Konfigurasi
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dokumentasi API otomatis ada di `http://localhost:8000/docs`. Basis data SQLite (`backend/skripsi.db`) dibuat otomatis, dan kolom baru ditambahkan sendiri saat aplikasi dimulai.

### 2. Frontend

```bash
npm install
cp .env.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Buka `http://localhost:3000`.

## Konfigurasi

Semua rahasia hanya di berkas env yang tidak di-commit (`backend/.env`, `.env.local`).

| Variabel | Fungsi |
|---|---|
| `SKRIPSI_NIM_API_KEY` | LLM tugas berat (NVIDIA NIM), wajib untuk penulisan draf |
| `SKRIPSI_GROQ_API_KEY`, `SKRIPSI_GEMINI_API_KEY` | LLM cepat dan cadangan |
| `SKRIPSI_SECRET_KEY` | Penandatangan token login (ganti di produksi) |
| `SKRIPSI_OPENALEX_API_KEY` | OpenAlex mewajibkan kunci |
| `SKRIPSI_CORE_API_KEY`, `SKRIPSI_SEMANTIC_SCHOLAR_API_KEY` | Opsional, menambah sumber dan kuota |
| `SKRIPSI_POLITE_EMAIL` | Email nyata untuk Crossref/Unpaywall |
| `SKRIPSI_ONESIGNAL_APP_ID`, `SKRIPSI_ONESIGNAL_API_KEY`, `SKRIPSI_APP_URL` | Push notification (opsional) |
| `NEXT_PUBLIC_API_URL` | Alamat backend untuk frontend |
| `NEXT_PUBLIC_ONESIGNAL_APP_ID` | App ID OneSignal untuk frontend (opsional) |

Daftar lengkap beserta penjelasannya ada di [`backend/.env.example`](backend/.env.example). Tanpa kunci sebuah penyedia, penyedia itu dilewati; fitur push tampil nonaktif sampai diisi.

## Pengujian

```bash
# backend
cd backend && pytest -q

# frontend
npx tsc --noEmit
npm run lint

# skenario dua jurusan dengan LLM dan API ilmiah sungguhan (backend harus berjalan)
node scripts/scenario-dual-domain.mjs
```

Jangan menjalankan `next build` biasa saat `next dev` aktif karena akan menimpa folder `.next`. Untuk build uji: `NEXT_DIST_DIR=.next-test npx next build`, lalu `next start -p 3100`.

## Deploy

- Frontend dapat dideploy ke Vercel atau host Node lain; set `NEXT_PUBLIC_API_URL` ke alamat backend.
- Backend dapat dijalankan dengan `uvicorn` di belakang HTTPS. Atur `SKRIPSI_CORS_ORIGINS` ke domain frontend, `SKRIPSI_SECRET_KEY` yang kuat, dan `SKRIPSI_DATABASE_URL` bila memakai Postgres.
- Push notification dan service worker membutuhkan HTTPS di produksi (localhost dikecualikan).

## Dokumentasi

- [`docs/prd-generator-skripsi-ai-lengkap.md`](docs/prd-generator-skripsi-ai-lengkap.md): kebutuhan produk
- [`docs/laporan_audit_bug_dan_rekomendasi_pengembangan_skripsiai.md`](docs/laporan_audit_bug_dan_rekomendasi_pengembangan_skripsiai.md): audit bug dan status perbaikan
- [`docs/beta-test-plan.md`](docs/beta-test-plan.md): rencana uji beta
- [`docs/DESIGN.md`](docs/DESIGN.md): acuan desain visual

## Keamanan dan privasi

- Kunci API tidak pernah dikirim ke browser; hanya `NEXT_PUBLIC_*` yang publik.
- Data akun, draf, dan data penelitian tersimpan di basis data backend milik Anda.
- Tautan pembimbing bersifat baca-saja dan dapat dicabut kapan saja; siapa pun yang memegang tautan dapat membukanya.
- Unduhan PDF rujukan memakai pengambilan yang aman terhadap SSRF.
