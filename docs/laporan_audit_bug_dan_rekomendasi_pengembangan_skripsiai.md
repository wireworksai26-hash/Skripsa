# Laporan Audit Teknis, Daftar Bug, & Roadmap Perbaikan Platform Skripsa

**Proyek:** Skripsa (Multi-Agent Thesis Generator PWA)

**Dokumen Uji:** `Students’ Voices on the Effectiveness of Peer-Presentations Followed by Teacher’.docx`

**Acuan Standar:** Buku Pedoman Penulisan Skripsi FBS Unimed

**Tanggal Evaluasi:** 7 November 2026

## 1. Ringkasan Eksekutif

Secara fungsional, *pipeline* dasar **Skripsa** sudah berhasil mengeksekusi alur *end-to-end* mulai dari pembuatan kerangka bab, penarikan referensi ber-DOI, penyusunan daftar isi otomatis, hingga penyisipan gambar diagram ke dalam format `.docx`.

Namun, dari sisi **kualitas substansi akademik**, **isolasi konteks antar-agen (*multi-agent orchestration*)**, dan **kepatuhan terhadap pedoman universitas**, masih ditemukan sejumlah *bug* kritis yang menyebabkan dokumen terlihat jelas sebagai hasil *auto-generation* mentah dan berisiko tinggi ditolak saat bimbingan.

## 2. Matriks Prioritas Perbaikan (Action Plan)

| Prioritas | Kode Bug | Kategori | Deskripsi Singkat Masalah | Dampak pada Pengguna | 
| ----- | ----- | ----- | ----- | ----- | 
| **P0 (Kritis)** | `BUG-01` | *Multi-Agent Context* | Duplikasi teks persis (*copy-paste*) antar-bab (Bab 1 disalin ke Bab 2 dan diulang 2 kali) serta di dalam subbab 3.3 dan 3.4. | Skripsi langsung dianggap cacat/plagiat diri sendiri (*self-plagiarism*). | 
| **P0 (Kritis)** | `BUG-02` | *Prompting / LLM Logic* | *Meta-writing*: AI menulis esai tentang "pentingnya membuat rumusan masalah/saran", bukan menuliskan isi rumusan masalah atau sarannya. | Bab 1 dan Bab 5 kehilangan komponen inti yang wajib dinilai dosen. | 
| **P0 (Kritis)** | `BUG-03` | *Content* Generation | Bab 4 tidak memiliki data empiris (kutipan wawancara/observasi) dan justru mengulang penjelasan teori metodologi Bab 3. | Melanggar aturan keaslian data; Bab 4 tidak menjawab Rumusan Masalah. | 
| **P1 (Tinggi)** | `BUG-04` | *Diagram Generator* | Diagram menggunakan *template* statis berbahasa Indonesia dan berlogika Kuantitatif (Variabel X/Y & Hipotesis) pada skripsi Kualitatif berbahasa Inggris, serta salah letak di Bab 4. | Kontradiksi metodologi yang fatal antara teks dan visualisasi. | 
| **P1 (Tinggi)** | `BUG-05` | *RAG / Citation Engine* | Sitasi `(Anonim, 2024)` dari dokumen *peer-review*, referensi tidak relevan (*off-topic*), jurnal >10 tahun (2011 & 2014), tidak ada nomor halaman, dan posisi sitasi di luar tanda titik. | Kredibilitas ilmiah rendah dan melanggar aturan pengutipan FBS Unimed. | 
| **P2 (Sedang)** | `BUG-06` | *Document Structure* | Struktur subbab menggunakan angka desimal (`1.1`, `1.2`) alih-alih sistem hierarki Unimed (`A.`, `1.`, `a.`), serta struktur subbab belum mengikuti pakem Kualitatif FBS Unimed. | Format ditolak oleh staf administrasi prodi atau dosen pembimbing. | 
| **P2 (Sedang)** | `BUG-07` | *Typography & Layout* | Paragraf raksasa (*wall of text* >600 kata di subbab 3.2), *typo* penggabungan teks judul bab (`CHAPTER IINTRODUCTION`), dan ketiadaan Bagian Awal (*Front Matter*). | Tampilan dokumen tidak rapi dan jumlah halaman isi (<20 hlm) belum mencapai syarat minimal 40 halaman. | 
| **P3 (Rendah)** | `BUG-08` | *File & String Handling* | Nama file `.docx` terpotong pada karakter apostrof (`Teacher’.docx`), tanda titik di akhir judul utama, dan *watermark* generator di halaman judul. | Mengurangi kesan profesional saat file diunduh pengguna. | 

## 3. Rincian Bug, Bukti di Dokumen, & Solusi Teknis

### P0 — Prioritas Kritis (Wajib Diperbaiki Segera)

#### `BUG-01`: Duplikasi Paragraf Antar-Bab & Intra-Bab (*Context Bleeding & Looping*)

* **Bukti pada Dokumen `.docx`:**

  1. **Bab II (`2.1 Theoretical Framework`):** Terdiri dari 8 paragraf. Paragraf 1–4 memiliki kalimat pembuka dan isi yang **identik** dengan paragraf pertama di subbab `1.1`, `1.2`, `1.3`, dan `1.4` pada Bab I. Lebih parah lagi, Paragraf 5–8 di subbab `2.1` mengulang kembali Paragraf 1–4 secara verbatim (kata demi kata), hanya berbeda nama sitasi di akhir paragraf (misal: paragraf 1 diakhiri `(Dionne, 2021)`, sedangkan paragraf 5 yang identik diakhiri `(Preece, 2025)`).

  2. **Bab III (`3.3 Data Collection Techniques`):** Paragraf pertamanya (*"The present study adopts a qualitative research approach..."*) menyalin ulang paragraf pembuka di subbab `3.1 Research Approach and Design`.

  3. **Bab III (`3.4 Data Analysis`):** Dua paragraf terakhir (*"The analysis of student voices in this study is therefore not a linear process..."* dan *"In conclusion, the application of the Miles and Huberman..."*) tercetak dua kali berturut-turut dengan pergantian sitasi di ujungnya.

* **Akar Masalah (*Root Cause*):**

  * Agen penulis subbab dipanggil dalam *loop* dengan *prompt template* yang sama atau menerima *history* teks Bab 1 secara mentah, sehingga LLM melakukan *pattern copying*.

  * Adanya mekanisme *retry* atau *chunking* untuk memenuhi target jumlah kata (*word count*), di mana hasil *generation* dari *loop* pertama dan kedua langsung digabungkan (`array.join()`) tanpa pengecekan kemiripan teks.

* **Solusi Teknis (*Engineering Fix*):**

  1. **Isolasi Prompt per Subbab:** Jangan pernah mengirimkan teks penuh Bab 1 ke dalam *prompt* Agen Bab 2. Kirimkan hanya objek *state* ringkas berisi `{"title":` "...", "variables": \["Peer-Presentations", "Teacher's Wrap-Up", "English` Learning"], "research_questions": [...]}`.

  2. **Deduplication Guardrail:** Tambahkan fungsi *post-processing* berbasis *n-gram overlap* atau *Cosine Similarity* ($\text{Similarity} \ge 0.75$) antar-paragraf. Jika paragraf baru memiliki kemiripan $\ge 75\%$ dengan paragraf sebelumnya, tolak output tersebut dan minta agen men-*generate* ulang dengan instruksi topik yang berbeda.

#### `BUG-02`: *Meta-Writing* (Menulis "Tentang" Subbab, Bukan "Isi" Subbab)

* **Bukti pada Dokumen `.docx`:**

  * Pada **`1.3 Research Questions and Objectives`**, tertulis: *"The* formulation of research questions and objectives represents a critical juncture in the architecture of scholarly inquiry... The primary research question *guiding this inquiry pertains to students’ perceptions..."* — Tidak ada satu pun kalimat tanya (`?`) atau poin daftar tujuan penelitian!

  * Pada **`5.2 Suggestions`**, tertulis 1 paragraf panjang (230 kata) yang membahas betapa pentingnya membuat saran dalam penelitian kualitatif (*"The formulation of actionable recommendations represents a critical component in closing the research cycle..."*), lalu ditutup dengan kalimat *"The following suggestions are therefore grounded in the rich tapestry of student narratives... (Dionne, 2021)"* — tetapi **poin-poin sarannya tidak pernah ditulis sama sekali**.

* **Akar Masalah (*Root Cause*):**

  * *Prompt* kemungkinan hanya berisi instruksi umum seperti: *"Write section 1.3 Research Questions and Objectives for a thesis titled X"* atau *"Write* a *paragraph about 5.2 Suggestions"*. Tanpa batasan skema output, LLM cenderung menulis esai deskriptif tentang definisi subbab tersebut.

* **Solusi Teknis (*Engineering Fix*):**

  * Terapkan **Structured Outputs (JSON Schema)** untuk subbab yang membutuhkan poin-poin spesifik:

    * **Skema Bab 1 (Rumusan Masalah & Tujuan):**

      ```
      {
        "intro_sentence": "Based on the background and focus of the study, the research questions are formulated as follows:",
        "research_questions": [
          "How do students perceive the implementation of peer-presentations followed by teacher's wrap-up in English learning?",
          "What are the perceived benefits and challenges voiced by students regarding the teacher's wrap-up session after peer-presentations?"
        ],
        "objectives_intro": "In line with the research questions, the objectives of this study are:",
        "research_objectives": [
          "To explore and describe students' voices on the implementation of peer-presentations followed by teacher's wrap-up.",
          "To identify the benefits and challenges experienced by students during the peer-presentation and teacher's wrap-up sequence."
        ]
      }
      
      ```

    * **Skema Bab 5 (`5.2 Suggestions`):** Wajibkan JSON mengembalikan 3 kategori saran sesuai standar skripsi kependidikan: `for_english_teachers`, `for_students`, dan `for_future_researchers`.

#### `BUG-03`: Ketiadaan Data Empiris & Pengulangan Metodologi di Bab IV

* Bukti pada Dokumen **`.docx`:**

  * Pada **`4.1 Description of the Data`** (Paragraf 1) dan **`4.2 Research Findings`** (Paragraf 1–4), teks kembali menjelaskan *mengapa metode kualitatif, wawancara semi-terstruktur, observasi, dan analisis tematik dipilih*. Ini adalah materi Bab III, bukan Bab IV.

  * Di akhir Paragraf 1 subbab `4.1`, tertulis janji palsu AI: *"The following paragraphs will detail the specific demographic characteristics of the participants, the setting in which the data was collected..."*, namun paragraf berikutnya langsung melompat ke kesimpulan umum tanpa ada data demografi maupun kutipan wawancara siswa.

* **Akar Masalah (*Root Cause*):**

  * Agen Bab IV tidak dibekali data atau *synthetic/placeholder dataset* untuk dianalisis, sehingga LLM mengarang narasi abstrak dan mengulang pembahasan metodologi agar mencapai batas panjang teks.

* **Solusi Teknis (*Engineering Fix*):**

  * **Opsi A (Mode Draft / Template):** Jika pengguna belum punya data lapangan, instruksikan Agen Bab IV untuk membuat **Tabel Ringkasan Tema Wawancara** dan menyisipkan **Placeholder Kutipan Transkrip** yang terstruktur (misal: `"[Excerpts from Student 1 (S1) Interview — Insert actual quote about lower speaking anxiety here]"`).

  * **Opsi B (Mode Data Input di PWA):** Sediakan fitur di UI PWA agar pengguna bisa mengunggah *file* CSV/Excel atau teks catatan hasil wawancara/kuesioner, lalu Agen Bab IV merangkum data riil tersebut menjadi temuan penelitian.

### P1 — Prioritas Tinggi (Kesesuaian Metodologi, Visualisasi & Referensi)

#### `BUG-04`: Diagram *Hardcoded* yang Salah Bahasa, Salah Metodologi, dan Salah Posisi

* **Bukti pada Dokumen `.docx`:**

  * Di akhir Bab IV (`4.3`), muncul **`Figure 4.1 Kerangka berpikir`** (berisi kotak *Landasan teori* $\rightarrow$ *Variabel X (independen)* $\rightarrow$ *pengaruh* $\rightarrow$ *Variabel Y (dependen) + Moderator/kontrol* $\rightarrow$ *Hipotesis penelitian*) dan **`Figure 4.2 Alur metodologi`** (berisi *Hipotesis terdukung? Ya / Tidak*).

* **Akar Masalah (*Root Cause*):**

  * Modul pembuat diagram menggunakan *template* Mermaid/flowchart statis yang di-*hardcode* untuk skripsi Kuantitatif berbahasa Indonesia, dan selalu disisipkan di akhir Bab IV.

* **Solusi Teknis (*Engineering Fix*):**

  1. **Dynamic Diagram Routing:** Buat logika pencabangan berdasarkan `methodology` (`qualitative` | `quantitative` | `ptk` | `rnd`) dan `language` (`id` | `en`).

  2. **Koreksi Penempatan Bab:**

     * Diagram *Conceptual Framework* (`Kerangka Konseptual`) wajib di-*render* di akhir **Bab II** (bukan Bab IV) dan diberi nomor **`Figure 2.1`** (atau `Gambar 2.1` / `Bagan 2.1` sesuai pedoman FBS Unimed hlm. 10–11).

     * Diagram *Research Procedure / Data Analysis Flow* wajib di-*render* di **Bab III** dan diberi nomor **`Figure 3.1`**.

#### `BUG-05`: Masalah Kualitas Sitasi, Referensi Kedaluwarsa, & Anomali `(Anonim, 2024)`

* **Bukti pada Dokumen `.docx`:**

  1. **Sitasi `(Anonim, 2024)`:** Muncul berkali-kali di dalam teks berbahasa Inggris. Di bagian `REFERENCES`, sumbernya adalah *Peer Review Report For: Effectiveness of peer-assisted teaching... (2024)*. API pencari jurnal mengambil dokumen *peer review report* tanpa nama penulis, lalu kode *fallback* mengubah `author == null` menjadi string `"Anonim"` (bahasa Indonesia).

  2. **Referensi *Off-Topic* & Kedaluwarsa:**

     * `Setiyaningrum, E. (2011)`: Berjudul *"The use of games in improving speaking skill by the fifth grade students of min ketitang, boyolali"*. Artikel tentang **permainan (games) di kelas 5 SD/MI tahun 2011** ini dipakai secara keliru untuk mengutip teori *teacher's wrap-up* pada mahasiswa perguruan tinggi! Selain itu, tahun 2011 melanggar syarat kemutakhiran referensi FBS Unimed (jurnal wajib 5–7 tahun terakhir, buku maksimal 10 tahun terakhir — Pedoman hlm. 3 & 35).

     * `Dionne, J. (2021)`: Bab buku berjudul *"Wrap-Up. How to Deliver Great Scientific Presentations"*. Mesin pencari referensi hanya mencocokkan kata kunci `"Wrap-Up"` dan `"Presentations"`, padahal buku ini membahas cara menutup presentasi ilmiah bagi ilmuwan, bukan sesi penguatan guru (*teacher's wrap-up*) di kelas bahasa Inggris.

  3. **Format Penempatan Sitasi:** Semua sitasi diletakkan di luar kalimat setelah tanda titik: `...instructional strategies. (Dionne, 2021)`.

* **Solusi Teknis (*Engineering Fix*):**

  1. **Filter Query API Referensi (OpenAlex / Semantic Scholar / CrossRef):**

     * Tambahkan filter wajib: `publication_year >= (current_year - 7)` (yaitu $\ge 2019$ untuk tahun 2026).

     * Filter tipe dokumen: `type IN ['journal-article', 'book', 'book-chapter']` dan `type NOT IN ['peer-review', 'dataset', 'editorial']`.

     * Filter penulis: Tolak artikel jika `authors == null` atau `authors.length` ==` 0`.

  2. **Semantic Reranking untuk Relevansi Referensi:** Jangan hanya menggunakan *keyword search* (`"wrap-up"`). Gunakan *embedding similarity* atau *LLM Reranker* untuk memastikan abstrak jurnal yang diambil benar-benar relevan dengan konteks *English Language Teaching (ELT) / Pedagogy*.

  3. **Format Sitasi & Daftar Rujukan Unimed:**

     * Masukkan sitasi **sebelum** titik kalimat terakhir dan sertakan halaman (atau gunakan format naratif/parentetis di tengah paragraf, bukan hanya ditempel di kalimat paling akhir setiap paragraf).

     * Sesuaikan format Daftar Rujukan dengan gaya FBS Unimed (Pedoman hlm. 28, 35, & Lampiran 16): tanpa tanda kurung pada tahun, contoh: `Charoensuk, V. 2026. Mapping Out the Importance-Difficulty Matrix...`

### P2 — Prioritas Sedang (Kepatuhan Pedoman FBS Unimed & Tata Letak)

#### `BUG-06`: Ketidaksesuaian Struktur Bab & Sistem Penomoran dengan Pedoman FBS Unimed

* **Bukti pada Dokumen `.docx` vs Pedoman FBS Unimed:**

  1. **Sistem Penomoran Subbab:** Dokumen saat ini memakai penomoran angka desimal (`1.1`, `1.2`, `2.1`). Menurut **Pedoman FBS Unimed Bagian M.c (hlm. 31–32)** dan **Lampiran 13 (hlm. 49)**, urutan penomoran yang wajib digunakan adalah:

     * Bab: Angka Romawi Besar (`BAB I`, `BAB II` / `CHAPTER I`, `CHAPTER II`)

     * Subbab: Huruf Kapital (`A.`, `B.`, `C.`)

     * Sub-subbab: Angka Arab (`1.`, `2.`, `3.`)

     * Anak sub-subbab: Huruf Kecil (`a.`, `b.`, `c.`) $\rightarrow$ `1)` $\rightarrow$ `a)` $\rightarrow$ `(1)` $\rightarrow$ `(a)`.

  2. **Struktur Subbab Penelitian Kualitatif (Pedoman hlm. 6, 14–15, 17):**

     * **CHAPTER I INTRODUCTION:**

       * `A. Background of the Study` (Latar Belakang)

       * `B. Focus of the Study` (Fokus Penelitian — menggantikan Identifikasi/Batasan Masalah pada kualitatif)

       * `C. Research Questions` (Rumusan Masalah — terpisah dari Tujuan)

       * `D. Objectives of the Study` (Tujuan Penelitian)

       * `E. Significance of the Study` (Manfaat Penelitian — wajib dipecah menjadi `1. Theoretical Significance` dan `2. Practical Significance`)

     * **CHAPTER II LITERATURE REVIEW:**

       * `A. Theoretical Framework` (Wajib dipecah menjadi sub-subbab variabel: `1. Students' Voices / Perceptions in EFL`, `2. Peer-Presentations in English Learning`, `3. Teacher's Wrap-Up / Debriefing Session`, dst.)

       * `B.` Operational` Definitions` (Definisi Operasional — disebutkan di Pedoman hlm. 6 untuk kualitatif)

       * `C. Review of Relevant Studies` (Hasil Penelitian yang Relevan)

       * `D. Conceptual Framework` (Kerangka Konseptual + Bagan)

     * **CHAPTER III RESEARCH METHOD:**

       * `A. Research Approach and Design`

       * `B. Data and Sources of Data` (Data dan Sumber Data Penelitian — memuat lokasi & subjek penelitian secara spesifik)

       * `C. Research Instruments` (Instrumen Pengumpulan Data)

       * `D. Data Collection Techniques`

       * `E. Trustworthiness of the Data` (Uji Kesahihan Data)

       * `F. Data Analysis Techniques`

     * **CHAPTER IV RESULTS AND DISCUSSION:**

       * `A. Research Findings / Results`

       * `B. Discussion`

#### `BUG-07`: Masalah Tipografi, Paragraf Raksasa (*Wall of Text*), & Kelengkapan Halaman

* **Bukti pada Dokumen `.docx`:**

  1. **Judul Bab Menyatu Tanpa Spasi/Enter:** Pada hasil ekstraksi dokumen, judul bab tertulis `CHAPTER IINTRODUCTION`, `CHAPTER IILITERATURE REVIEW`, `CHAPTER IIIRESEARCH METHOD`, `CHAPTER IVRESULTS AND DISCUSSION`, `CHAPTER VCONCLUSION AND SUGGESTIONS`. Pada *template* `.docx`, pastikan ada *line break* (`<w:br/>` atau paragraf terpisah) antara `CHAPTER I` dan `INTRODUCTION`.

  2. **Paragraf Raksasa di Subbab `3.2 Research Subjects and Site`:** Seluruh subbab `3.2` hanya terdiri dari **1 paragraf sepanjang 928 kata (46 kalimat)** yang berputar-putar mengulang kalimat yang mirip! Batasi panjang paragraf di *system prompt* maksimal **120–180 kata (5–8 kalimat)** per paragraf.

  3. **Bagian Awal (*Front Matter*) & Bagian Akhir (*Back Matter*) Belum Ada:**

     * Belum ada *Cover Page* sesuai standar Unimed (Logo diameter $4.5\text{ cm}$, huruf kapital *Times New Roman* $14\text{ pt}$ spasi $1$), Halaman Persetujuan, Halaman Pengesahan, Pernyataan Orisinalitas, *Preface* (`Prakata`), dan **Abstrak** 2 Bahasa (`Abstract` & `Abstrak`) yang terdiri dari 4 alinea (Tujuan, Teori, Metode, Hasil) maksimal 250 kata (Pedoman hlm. 29–30 & Lampiran 6–12).

### P3 — Prioritas Rendah (UI/UX & Penanganan File)

#### `BUG-08`: Nama File Terpotong, Tanda Baca Judul, & *Watermark*

* **Bukti pada Dokumen `.docx`:**

  * Nama file yang diunduh terpotong tepat pada karakter kutip tunggal: `Students’ Voices on the Effectiveness of Peer-Presentations Followed by Teacher’.docx`.

  * Judul di halaman pertama diakhiri tanda titik (`.`): `...in English Learning.` (Judul skripsi tidak boleh diakhiri tanda titik).

* **Solusi Teknis (*Engineering Fix*):**

  * Gunakan fungsi *slugify / sanitize filename* sebelum membuat nama file unduhan (misal: ganti spasi dengan `_`, hapus tanda kutip/karakter non-alfanumerik, dan batasi panjang karakter secara aman: `Students_Voices_on_Peer_Presentations_Skripsi.docx`).

## 4. Rekomendasi Penambahan Tabel & Gambar/Bagan yang Masuk Akal

Agar draf skripsi yang dihasilkan **Skripsa** terlihat berbobot, realistis, dan memenuhi target minimal **40 halaman isi** secara bermakna (bukan dengan mengulang paragraf), *engine* kamu sebaiknya men-*generate* tabel dan bagan kontekstual berikut di setiap bab:

### A. Bab II (Literature Review)

#### 1. Tabel Perbandingan Penelitian Terdahulu (*Summary Table of Relevant Studies*)

Letakkan di akhir subbab **Review of Relevant Studies**. Tabel ini merangkum jurnal-jurnal yang ditarik dari API referensi dan membandingkannya dengan penelitian pengguna:

| No. | Author(s) & Year | Research Title | Methodology & Subjects | Key Findings | Research Gap / Relevance to Current Study | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 1. | Charoensuk (2026) | Mapping Out the Importance-Difficulty Matrix... | Quantitative Survey; 120 EFL Undergraduates | Students find organizing ideas and pronunciation most difficult during oral presentations. | Focuses on presentation difficulty; has not explored the role of teacher's wrap-up after peer presentations. | 
| 2. | Rasdi & Rusli (2026) | Students’ Perceptions of Nonverbal Communication... | Qualitative Interview; Tertiary ESL Learners | Peer observation helps students notice kinesics and vocalics in speaking. | Examines nonverbal aspects; the current study expands on how teacher synthesis consolidates linguistic accuracy. | 
| 3. | Preece (2025) | Voices in Forensics: Exploring Student Perceptions... | Mixed-Methods; Undergraduate Students | Oral presentations build peer engagement but require structured instructor feedback. | Conducted in science education; the current study adapts the inquiry to an EFL speaking classroom at FBS Unimed. | 

#### 2. Bagan Kerangka Konseptual (*Conceptual Framework Diagram* — `Figure 2.1`)

Ganti diagram *Variabel X/Y* yang salah tadi dengan diagram alur konseptual yang sesuai dengan judul dan metode kualitatif:

```
graph TD
    A[EFL Speaking Classroom Context] --> B[Stage 1: Peer-Presentations]
    B --> B1[Student-Led Delivery & Peer Q&A]
    B1 --> B2[Strengths: Lower Anxiety, Active Engagement, Peer Modeling]
    B1 --> B3[Limitations: Linguistic Errors & Unclear Concepts]
    B2 --> C[Stage 2: Teacher's Wrap-Up Session]
    B3 --> C
    C --> C1[Content Synthesis, Concept Clarification & Error Correction]
    C1 --> D[Students' Voices / Perceptions]
    D --> D1[Affective Dimension: Confidence & Motivation]
    D --> D2[Cognitive & Linguistic Dimension: Comprehension & Speaking Accuracy]
    D1 --> E[Perceived Effectiveness in English Learning]
    D2 --> E

```

### B. Bab III (Research Method)

#### 1. Tabel Profil Subjek / Partisipan Penelitian (*Participant Demographic Table* — `Table 3.1`)

Di subbab **Data and Sources of Data**, tambahkan tabel demografi partisipan (gunakan *placeholder* yang jelas agar mahasiswa tinggal menyesuaikan angkanya):

| Participant Code | Pseudonym / Initial | Gender | Semester / Class | Role in Peer-Presentation | Self-Reported Speaking Anxiety Level | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| S1 | `[Initial 1]` | Female | 4th Semester / Class A | Presenter & Audience | Low | 
| S2 | `[Initial 2]` | Male | 4th Semester / Class A | Presenter & Audience | Moderate | 
| S3 | `[Initial 3]` | Female | 4th Semester / Class A | Presenter & Audience | High | 
| S4 | `[Initial 4]` | Male | 4th Semester / Class B | Presenter & Audience | Moderate | 
| S5 | `[Initial 5]` | Female | 4th Semester / Class B | Presenter & Audience | High | 

#### 2. Tabel Kisi-Kisi Instrumen Wawancara (*Interview Blueprint / Grid* — `Table 3.2`)

Sangat disukai oleh dosen pembimbing dan penguji karena membuktikan bahwa pertanyaan wawancara diturunkan langsung dari teori di Bab II:

| No. | Aspect / Indicator | Sub-Indicators | Question Items | Total Items | 
| ----- | ----- | ----- | ----- | ----- | 
| 1. | Perceptions of Peer-Presentations | Preparation, peer interaction, speaking confidence, and audience engagement | Q1, Q2, Q3, Q4 | 4 | 
| 2. | Perceptions of Teacher's Wrap-Up | Clarity of summary, grammar/pronunciation correction, and concept consolidation | Q5, Q6, Q7, Q8 | 4 | 
| 3. | Perceived Challenges & Suggestions | Time management, peer feedback quality, and preferred wrap-up timing | Q9, Q10 | 2 | 
| **Total** |  |  |  | **10 Items** | 

#### 3. Bagan Alur Analisis Data Interaktif Miles & Huberman (`Figure 3.1`)

Khusus untuk subbab **Data Analysis Techniques**, buat diagram model interaktif Miles, Huberman, & Saldaña:

```
graph LR
    A[Data Collection<br/>Interviews & Observations] --> B[Data Condensation / Reduction<br/>Coding & Theme Grouping]
    A --> C[Data Display<br/>Thematic Matrices & Excerpts]
    B <--> C
    B <--> D[Conclusion Drawing & Verification<br/>Triangulation & Member Checking]
    C <--> D
    A <--> D

```

### C. Bab IV (Results and Discussion)

#### 1.
---

## 5. Status Perbaikan (7 November 2026)

Diverifikasi dengan membuat ulang skripsi uji yang sama (judul Inggris, kualitatif, Pendidikan Bahasa Inggris) memakai LLM sungguhan, lalu diukur dengan metrik yang sama seperti audit. Tes regresi: `backend/tests/test_quality.py`, `test_relevance.py`.

| Kode | Status | Perbaikan | Hasil ukur ulang |
| ----- | ----- | ----- | ----- |
| `BUG-01` | Selesai | Teks subbab lain tidak lagi dikirim ke LLM (hanya judulnya); setiap lanjutan & hasil akhir dibersihkan dari paragraf yang ≥60% sama (5-gram, abaikan sitasi) dengan subbab ini atau subbab lain (`agents/quality.py`). | 11 → 0 paragraf duplikat |
| `BUG-02` | Selesai | Rumusan masalah, tujuan, dan saran ditulis lewat JSON terstruktur lalu disusun kode (`agents/structured.py`); ekspor mempertahankan daftar bernomor. | 1.3: 4 pertanyaan; 1.4: 4 tujuan; 5.2: 9 saran per sasaran |
| `BUG-03` | Selesai (opsi A + data tabel) | Tanpa data lapangan, Bab IV disusun per tema dengan penanda `[DATA: …]` (disorot kuning di DOCX); tabel hasil yang disimpan pengguna dipakai sebagai data. Opsi B (unggah transkrip) belum. | 4.1: 30 penanda, tanpa temuan karangan |
| `BUG-04` | Selesai | Preset diagram mengikuti metode & bahasa (kerangka konseptual kualitatif, Miles–Huberman, ADDIE); grafik/diagram/tabel punya bab tujuan dan bernomor per bab. | Figure 2.1 di Bab II, Table 3.1 di Bab III |
| `BUG-05` | Sebagian | Karya tanpa penulis & jenis non-artikel (peer-review, editorial, dataset) dibuang; penyaring relevansi LLM; batas bawaan 10 tahun (opsi 5 tahun); sitasi dipindah sebelum titik. Format daftar pustaka khas Unimed (tahun tanpa kurung) belum. | 0 "Anonim"; 9 rujukan tak relevan dibuang |
| `BUG-06` | Sebagian | Templat kualitatif bawaan mengikuti struktur audit; pilihan penomoran subbab "A., B." saat ekspor. Sub-subbab `1.`/`a.` & templat khusus FBS Unimed belum (bisa lewat unggah PDF pedoman). | |
| `BUG-07` | Sebagian | Paragraf dibatasi ±180 kata (prompt + pemecah otomatis). Halaman awal (pengesahan, abstrak dua bahasa, prakata) belum dibuat. | Paragraf terpanjang 1.122 → 180 kata |
| `BUG-08` | Selesai | Nama berkas dipotong di batas kata tanpa tanda kutip; titik akhir judul dibuang; tanda air generator dipindah ke metadata dokumen. | |

Catatan: "CHAPTER IINTRODUCTION" bukan cacat di berkas DOCX (ada pemisah baris `<w:br/>`); gabungan itu muncul dari alat ekstraksi teks.
