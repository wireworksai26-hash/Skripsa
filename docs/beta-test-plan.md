# Rencana Pengujian Beta Dua Jurusan (Fase 4)

Tujuan: memastikan alur Skripsa bekerja untuk dua kelompok pengguna di PRD, yaitu **Informatika** (Persona A) dan
**Pendidikan Bahasa Inggris** (Persona B), serta pengguna awam (Persona C), sebelum dibuka ke penguji sungguhan.

## 1. Pemeriksaan otomatis (jalankan dulu)

| Perintah | Isi | Waktu |
|---|---|---|
| `cd backend && .venv\Scripts\python -m pytest -q` | Tes unit dan API tanpa jaringan: parser PDF, statistik, RAG, sitasi, SSRF, templat | ± 15 dtk |
| `node scripts/scenario-dual-domain.mjs` | Skenario nyata dua jurusan dengan LLM dan API ilmiah sungguhan (28 pemeriksaan) | ± 2,5 mnt |
| `npx tsc --noEmit` dan `npx eslint src` | Tipe dan lint frontend | ± 30 dtk |

Skenario otomatis memeriksa per jurusan: templat mengikuti metode, judul dari LLM, sumber khusus bidang tampil
(arXiv untuk Informatika, ERIC untuk Bahasa Inggris), tidak ada sumber yang gagal, penanda sitasi benar-benar tertulis di
teks, kalimat yang disorot adalah kutipan nyata dari abstrak, uji statistik, pertanyaan sidang dari LLM, dan data
tersimpan di server.

## 2. Daftar periksa untuk penguji manusia

Tiap penguji mengerjakan satu skripsi nyata (atau topik contoh) dari Langkah 1 sampai ekspor `.docx`, lalu mengisi
kolom hasil. Catat waktu per langkah dan setiap kebingungan.

### A. Informatika (kuantitatif atau R&D)
- [ ] Langkah 1: unggah **PDF pedoman kampus sendiri**. Margin, huruf, spasi, gaya sitasi, dan bab terbaca benar? Kutipan bukti bertanda ✓?
- [ ] Langkah 3: ada artikel arXiv di daftar. DOI aktif? Tombol "Teks penuh" membuka PDF yang benar?
- [ ] Langkah 4: klik penanda sitasi. PDF terbuka, halaman benar, kalimat tersorot kuning sesuai klaim?
- [ ] Langkah 5: diagram **PlantUML** (use case, class, sequence, activity) tampil benar dan lolos ke Bab IV.
- [ ] Langkah 5: unggah CSV hasil uji. Rerata, SD, uji t atau ANOVA cocok dengan perhitungan di Excel/SPSS?
- [ ] Langkah 6: pertanyaan sidang menyebut hal konkret dari skripsi (bukan pertanyaan umum)?
- [ ] DOCX: margin, huruf, spasi sesuai pedoman kampus? Daftar isi terisi setelah memilih "Ya" saat Word meminta pembaruan?

### B. Pendidikan Bahasa Inggris (kualitatif atau kuantitatif)
- [ ] Langkah 3: ada artikel ERIC di daftar; abstrak berbahasa Inggris terbaca dan dikutip dengan benar?
- [ ] Langkah 4: draf berbahasa Indonesia baku, sitasi gaya APA 7th, nama penulis tidak terbalik.
- [ ] Langkah 5: kerangka berpikir (Mermaid atau PlantUML), tabel hasil uji pre-post (t berpasangan).
- [ ] Langkah 6: daftar pustaka APA 7th dan IEEE (tombol pratinjau) rapi: tahun, huruf miring jurnal, DOI.
- [ ] DOCX: tabel dan gambar bernomor "Tabel 4.n" dan "Gambar 4.n", muncul di Daftar Tabel dan Daftar Gambar.

### C. Pengguna awam (non-teknis)
- [ ] Bisa menyelesaikan Langkah 1 sampai 6 tanpa bantuan dan tanpa menulis prompt?
- [ ] Pesan error dipahami (mis. LLM mati, PDF hasil pindai, sumber gagal)?
- [ ] Tidak ada teks template yang terasa palsu; setiap sitasi bisa ditelusuri ke sumbernya.

## 3. Kriteria lulus beta

| Kriteria | Ambang |
|---|---|
| Penguji menyelesaikan alur sampai ekspor `.docx` | ≥ 80% |
| Sitasi di draf yang tersorot tepat di PDF (bila PDF tersedia) | ≥ 70% dari yang diklik |
| Parser PDF pedoman: margin/huruf/spasi benar tanpa koreksi | ≥ 80% dari pedoman berteks |
| Hasil uji statistik sama dengan Excel/SPSS | 100% pada data uji |
| Waktu draf per subbab | < 60 dtk (LLM berfungsi) |
| Kegagalan tak tertangani (halaman putih, error mentah) | 0 |

## 4. Keterbatasan yang sudah diketahui (beri tahu penguji)

- PDF pedoman **hasil pindai** belum didukung (tidak ada OCR); unggah PDF berteks.
- Ukuran kertas selain A4 terbaca tetapi ekspor tetap A4.
- Stabilo kuning mencocokkan kalimat dari **abstrak** ke naskah PDF; bila abstrak diparafrasekan, kecocokan bisa rendah
  dan penguji diminta memeriksa manual (viewer menampilkan pesan).
- Rujukan tanpa tautan PDF terbuka hanya menampilkan kalimat abstrak. Unpaywall perlu `SKRIPSI_POLITE_EMAIL` berisi email
  asli di `backend/.env` agar menambah tautan PDF.
- OpenAlex mewajibkan kunci API sejak 13 Februari 2026; tanpa kunci kuotanya kecil.
- Uji lanjut (post hoc) setelah ANOVA belum tersedia.
- Daftar isi dan nomor halaman terisi setelah Word memperbarui bidang saat berkas dibuka.

## 5. Mengumpulkan umpan balik

Untuk setiap temuan catat: jurusan, langkah, apa yang diharapkan, apa yang terjadi, tangkapan layar, dan (bila ada) pesan
error. Pesan error dari LLM menyebut penyedia yang gagal sehingga mudah ditelusuri di `backend/.env`.
