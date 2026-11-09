# Product Requirement Document (PRD): Platform Multi-Agent AI Generator Skripsi & Analisis Akademik Terintegrasi

## 1. Visi Produk & Ringkasan Eksekutif

Platform Generator Skripsi AI dirancang sebagai platform penulisan akademik cerdas terintegrasi (*Software as a Service / SaaS*) yang diciptakan khusus untuk membantu mahasiswa jenjang Sarjana (S1) dan Magister (S2) di Indonesia dalam menyusun skripsi dan tugas akhir. Platform ini dibangun di atas arsitektur *Multi-Agent System* dan *Retrieval-Augmented Generation* (RAG) presisi tinggi untuk menjamin bahwa draf yang dihasilkan runtut, memenuhi standar ejaan dan struktur ilmiah baku, bebas dari halusinasi sitasi, serta sepenuhnya adaptif terhadap pedoman selingkung khas dari perguruan tinggi mana pun di Indonesia.

Penyusunan skripsi di Indonesia memiliki tantangan unik berupa tingginya variasi aturan penulisan antar-kampus serta maraknya halusinasi sitasi pada alat kecerdasan buatan generik. Platform ini memecahkan hambatan tersebut dengan menghadirkan alur kerja tanpa *prompting* rumit (*promptless workflow*), integrasi basis data jurnal ilmiah publik yang gratis, penanda visual kutipan asli (*yellow highlighter*), serta simulasi bimbingan dan ujian bersama agen AI berorientasi peran (Dosen Pembimbing, Dosen Penguji, Penulis Akademik, dan Agen Pengawas Kualitas).

---

## 2. Profil Pengguna & User Stories

Perancangan platform mengacu pada pemetaan kebutuhan pengguna yang mencakup dua bidang studi utama (Informatika dan Pendidikan Bahasa Inggris) serta kelompok pengguna umum dari latar belakang non-teknis.

### 2.1 Persona Utama Pengguna

Tabel berikut merangkum profil persona target pengguna platform beserta fokus kebutuhan penulisan ilmiah mereka.

| Persona Pengguna | Latar Belakang Studi | Fokus Kebutuhan Riset & Penulisan |
| --- | --- | --- |
| **Persona A (Developer / AI Engineer)** | Teknik Informatika / Sistem Informasi | Penyusunan Bab 3 & 4: perancangan UML, diagram arsitektur sistem, pseudokode algoritma, uji statistik kuantitatif, serta dokumentasi rekayasa perangkat lunak. |
| **Persona B (Language Educator / Practitioner)** | Pendidikan Bahasa Inggris (ELT / TEFL) | Penyusunan Bab 2, 3, & 4: landasan teori *Second Language Acquisition* (SLA), instrumen penelitian eksperimen/kualitatif, rubrik penilaian *speaking/writing*, serta analisis transkrip wawancara. |
| **Persona C (General Undergraduate Student)** | Mahasiswa Awam (Non-Teknis) | Antarmuka berbasis formulir sederhana tanpa *prompting*, panduan berurutan dari penentuan judul hingga kesimpulan, serta ekspor dokumen langsung ke format Microsoft Word (DOCX). |

### 2.2 User Stories

* **Formulir Tanpa Prompting**: Sebagai mahasiswa awam, saya ingin menginput ide kasar penelitian saya ke dalam formulir sederhana tanpa harus menyusun *prompt* yang rumit, sehingga sistem *backend* secara otomatis menghasilkan kerangka draf yang terstruktur dan bermutu tinggi.
* **Format Kustom Kampus**: Sebagai mahasiswa, saya ingin mengunggah PDF pedoman skripsi dari kampus saya sendiri agar struktur bab, ukuran margin, jenis font, spasi, dan gaya sitasi draf skripsi saya sesuai 100% dengan aturan resmi institusi saya.
* **Verifikasi Sitasi Nyata**: Sebagai mahasiswa, saya ingin setiap sitasi yang dihasilkan dapat diklik dan menampilkan cuplikan teks asli dari buku atau artikel jurnal ilmiah dengan penanda stabilo kuning beserta nomor halaman dan DOI aktifnya, sehingga dosen pembimbing dapat memverifikasi keaslian sumber rujukan saya.
* **Simulasi Bimbingan Multi-Agent**: Sebagai mahasiswa, saya ingin draf tulisan saya ditinjau oleh agen AI berkepribadian Dosen Pembimbing dan Dosen Penguji sebelum difinalisasi, agar saya mendapatkan kritik konstruktif dan kesiapan menghadapi seminar proposal maupun sidang skripsi.

---

## 3. Spesifikasi Fitur Utama Produk

Platform ini mengintegrasikan delapan modul fitur utama yang saling terhubung dalam satu *pipeline* pemrosesan data.

### 3.1 Module 1: Prompt Orchestration Engine (Promptless Input System)

Pengguna awam sering kali mengalami kendala *trial & error* saat menuliskan instruksi (*prompting*) pada AI umum, yang menghasilkan jawaban terlalu dangkal atau tidak sesuai kaidah akademik. 

Modul ini mengeliminasi kebutuhan *prompting* manual dengan antarmuka formulir terstruktur. Pengguna cukup mengisi beberapa bidang dasar: *Topik Utama*, *Variabel Penelitian (X dan Y)*, *Lokasi/Subjek Penelitian*, dan *Metode yang Diinginkan*. Di sisi *backend*, *Prompt Orchestrator Engine* secara otomatis menggabungkan input tersebut dengan *system prompt* akademis, batasan pola penulisan *piramida terbalik* untuk Bab 1, kriteria kesenjangan penelitian (*research gap*), serta regulasi tata bahasa baku sesuai Kamus Besar Bahasa Indonesia (KBBI) dan Pedoman Umum Ejaan Bahasa Indonesia (PUEBI/EYD V).

### 3.2 Module 2: Dynamic Campus Template Engine & PDF Parser

Format penulisan skripsi di Indonesia berbeda-beda antar perguruan tinggi. Sebagai contoh, susunan bab dan sub-bab pada Universitas Multimedia Nusantara, Universitas Indonesia, Unika Atma Jaya, maupun Universitas Widyatama memiliki penamaan dan urutan spesifik.

Modul ini menyediakan dua mekanisme penyesuaian format:
1. **Templat Bawaan Standar Nasional**: Menyediakan kerangka baku 5 Bab (Bab I Pendahuluan, Bab II Landasan Teoris/Tinjauan Pustaka, Bab III Metode Penelitian, Bab IV Hasil dan Pembahasan, serta Bab V Simpulan dan Saran) untuk jalur riset Kuantitatif maupun Kualitatif.
2. **Custom Guideline PDF Parser**: Pengguna dapat mengunggah file PDF buku pedoman skripsi dari kampus masing-masing. *Parser Engine* berbasis LLM akan membaca dokumen tersebut dan mengekstrak aturan selingkung menjadi konfigurasi JSON dinamis yang mencakup: struktur bab dan sub-bab wajib, batas margin halaman (seperti standar 4-4-3-3 cm), jenis dan ukuran font, spasi antar-baris, hingga gaya sitasi resmi yang diwajibkan.

### 3.3 Module 3: Multi-Source Scientific API Integrator (100% Free Tier Focus)

Untuk memastikan seluruh rujukan bersumber dari publikasi ilmiah nyata tanpa biaya langganan tambahan, platform terhubung secara langsung ke berbagai basis data dan API ilmiah publik yang bebas biaya.

* **OpenAlex API**: Penarikan metadata ilmiah global dari lebih dari 250 juta artikel ilmiah terindeks.
* **Crossref REST API**: Resolusi dan pemastian keaktifan DOI (*Digital Object Identifier*).
* **Semantic Scholar API**: Pengambilan abstrak, grafik sitasi (*citation graph*), dan indikator *influential citations*.
* **ERIC API**: Repositori khusus untuk artikel ilmiah bidang ilmu pendidikan, linguistik, dan *English Language Teaching* (ELT).
* **DOAJ API**: Direktori jurnal *open-access* internasional terakreditasi.
* **GARUDA / SINTA Integrator**: Penarikan rujukan jurnal nasional Indonesia yang terindeks SINTA 1 hingga SINTA 6.
* **arXiv API**: Repositori artikel ilmiah *pre-print* bidang Informatika, Kecerdasan Buatan, dan Rekayasa Perangkat Lunak.

### 3.4 Module 4: Visual Citation Highlight & Source Grounding Viewer

Salah satu risiko terbesar penggunaan AI dalam penulisan ilmiah adalah referensi palsu atau halusinasi sitasi. Modul ini menghadirkan fitur verifikasi transparan berkonsep *Visual Grounding*.

Saat agen AI menyusun draf paragraf, setiap klaim faktual dihubungkan secara presisi ke segmen teks asli dari jurnal atau buku rujukan. Pada antarmuka dokumen, pengklikan teks sitasi akan membuka *PDF Reader Viewer* di panel samping. Sistem secara otomatis menggulir (*auto-scroll*) ke halaman yang relevan dan menandai kalimat rujukan dengan warna **stabilo kuning (yellow highlight)**, lengkap dengan informasi nomor halaman, nama penulis, tahun publikasi, dan tautan DOI yang aktif.

### 3.5 Module 5: Auto Citation Engine & Bibliography Generator

Modul ini mengelola penulisan rujukan dalam teks (*in-text citation*) dan pembentukan Daftar Pustaka secara otomatis.

* **Format Sitasi Dalam Teks**: Disesuaikan secara otomatis dengan gaya sitasi kampus (seperti format APA 7th Edition: *(Suleeman & Sekarasih, 2018)*, format IEEE: *[1]*, atau format Chicago).
* **Generator Daftar Pustaka Otomatis**: Menyusun seluruh referensi yang dikutip di bagian akhir dokumen secara otomatis, berurutan alfabetis, memiliki format *hanging indent* (1 cm), serta melampirkan tautan DOI yang valid dan dapat diuji keaktifannya oleh dosen pembimbing.

### 3.6 Module 6: Multi-Agent Persona Skills System

Platform mengimplementasikan empat agen AI cerdas dengan kepribadian dan *skill set* akademik khusus yang bekerja secara berurutan (*sequential chaining*).

Tabel berikut mendeskripsikan peran, fungsi utama, dan luaran dari masing-masing agen dalam platform.

| Nama Agen | Peran Persona | Fungsi & Tanggung Jawab Utama |
| --- | --- | --- |
| **Advisor Agent** | Dosen Pembimbing | Memberikan bimbingan konstruktif, memperjelas urgensi latar belakang masalah, mempertajam kerangka pemikiran, serta memastikan adanya kebaruan ilmiah (*novelty/research gap*). |
| **Examiner Agent** | Dosen Penguji | Menguji validitas metodologi riset secara kritis, menantang konsistensi antara rumusan masalah dan kesimpulan, serta menyusun simulasi daftar pertanyaan sidang beserta saran jawabannya. |
| **Academic Writer Agent** | Penulis Akademik | Menyusun draf narasi per sub-bab berbasis konteks RAG, menjaga keruntutan paragraf, menerapkan bahasa Indonesia baku (EYD V), serta mengeliminasi kalimat *filler*. |
| **Quality Guardrail Agent** | Pengawas Kualitas (Validator) | Mengecek ketercapaian target jumlah kata (*word count*) per bab, memverifikasi keaktifan seluruh link DOI sitasi, serta mengecek kepatuhan margin dan tata letak dokumen. |

### 3.7 Module 7: Title & Research Ideation Recommendation Engine

Modul ini membantu mahasiswa pada tahap awal penelitian yang belum memiliki arah riset yang jelas:
* **Generator Judul Otomatis**: Menghasilkan 5 hingga 10 opsi judul skripsi yang spesifik, relevan dengan tren riset terbaru, serta mematuhi kaidah penulisan judul yang baku.
* **Analisis Celah Penelitian (Gap Analysis)**: Menganalisis 5 hingga 10 artikel jurnal relevan dan mengekstrak celah penelitian yang belum diselesaikan oleh peneliti sebelumnya.
* **Rekomendasi Desain Metodologi**: Memberikan masukan teknik pengambilan sampel (*sampling technique*) dan desain riset yang sesuai dengan topik penelitian yang dipilih.

### 3.8 Module 8: Automatic Chart, Table, & Diagram Visualizer Engine

Penelitian akademik membutuhkan visualisasi data yang jelas untuk memperkuat pembuktian di Bab 4 (Hasil dan Pembahasan).

* **Modul Kuantitatif**: Mengolah data mentah input (file CSV/Excel atau data hasil pengujian) menjadi tabel ringkasan statistik (seperti nilai Mean, Standard Deviation, T-Test, ANOVA). Modul ini mengekspor grafik dinamis (bar chart, line graph, pie chart) beresolusi tinggi (300 DPI) berbasis library Python *Plotly* atau *Matplotlib*.
* **Modul Kualitatif & Konseptual**: Mengekstrak alur pemikiran kualitatif atau arsitektur sistem menjadi diagram visual berbasis sintaks **PlantUML** dan **MermaidJS**. Diagram yang dihasilkan mencakup Diagram Kerangka Berpikir (*Conceptual Framework*), Flowchart Metodologi, serta Diagram UML (Use Case Diagram, Class Diagram, Activity Diagram) untuk jurusan Informatika.

---

## 4. Arsitektur Multi-Agent & Alur Pemrosesan Data

Arsitektur sistem dibangun berdasarkan prinsip modularisasi tugas agen (*Agentic Workflow*). Setiap agen berinteraksi melalui *state manager* yang terpusat untuk memastikan bahwa hasil kerja satu agen menjadi konteks input yang tervalidasi bagi agen berikutnya.

```
[ User Input Form (Promptless) ]
               │
               ▼
   [ Prompt Structurer Agent ]
               │
               ▼
   [ Planner / Outline Agent ]
               │
               ▼
┌──────────────┴──────────────┐
▼                             ▼
[ Literature RAG Agent ]     [ Campus Template Agent ]
(OpenAlex / Crossref API)    (Parses Guideline PDF to JSON)
│                             │
└──────────────┬──────────────┘
               ▼
   [ Academic Writer Agent ]
 (Drafting Per Sub-Bab & EYD)
               │
               ▼
   [ Visual & Data Agent ]
 (Plotly Charts & PlantUML)
               │
               ▼
┌──────────────┴──────────────┐
▼                             ▼
[ Advisor Agent (Pembimbing) ] [ Examiner Agent (Penguji) ]
(Review Logic & Novelty)      (Stress-Test & Defense Qs)
│                             │
└──────────────┬──────────────┘
               ▼
   [ Quality Guardrail Agent ]
 (Check Word Count & DOI Links)
               │
               ▼
   [ Final Document Output ]
 (DOCX File / Interactive UI)
```

---

## 5. Skema Basis Data & Spesifikasi JSON

### 5.1 JSON Schema: Campus Guideline Template (`campus_template.json`)

Struktur JSON ini digunakan oleh *Campus Template Engine* untuk mengunci format draf skripsi agar sesuai dengan pedoman institusi.

```json
{
  "title": "CampusGuidelineTemplate",
  "type": "object",
  "properties": {
    "campus_id": { "type": "string" },
    "campus_name": { "type": "string" },
    "faculty": { "type": "string" },
    "degree_level": { "type": "string", "enum": ["S1", "S2"] },
    "page_setup": {
      "type": "object",
      "properties": {
        "paper_size": { "type": "string", "default": "A4" },
        "margins_cm": {
          "type": "object",
          "properties": {
            "top": { "type": "number" },
            "left": { "type": "number" },
            "bottom": { "type": "number" },
            "right": { "type": "number" }
          },
          "required": ["top", "left", "bottom", "right"]
        },
        "font_family": { "type": "string", "default": "Times New Roman" },
        "font_size_pt": { "type": "integer", "default": 12 },
        "line_spacing": { "type": "number", "default": 1.5 },
        "paragraph_indent_cm": { "type": "number", "default": 1.0 }
      },
      "required": ["paper_size", "margins_cm", "font_family", "font_size_pt", "line_spacing"]
    },
    "citation_style": { "type": "string", "enum": ["APA_7TH", "IEEE", "CHICAGO", "HARVARD"] },
    "chapters": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "chapter_number": { "type": "string" },
          "chapter_title": { "type": "string" },
          "sub_sections": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "code": { "type": "string" },
                "title": { "type": "string" },
                "target_words": { "type": "integer" }
              },
              "required": ["code", "title", "target_words"]
            }
          }
        },
        "required": ["chapter_number", "chapter_title", "sub_sections"]
      }
    }
  },
  "required": ["campus_id", "campus_name", "page_setup", "citation_style", "chapters"]
}
```

### 5.2 Skema Relasional Basis Data (PostgreSQL)

Struktur tabel relasional dirancang untuk mendukung penyimpanan data pengguna, draf skripsi per sub-bab, serta *metadata grounding* sitasi.

```sql
-- Tabel Pengguna (Mahasiswa)
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    major_name VARCHAR(100) NOT NULL,
    campus_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabel Proyek Skripsi (Theses)
CREATE TABLE theses (
    thesis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    research_method VARCHAR(50) CHECK (research_method IN ('KUANTITATIF', 'KUALITATIF', 'MIXED_METHODS', 'RND')),
    domain_category VARCHAR(100) CHECK (domain_category IN ('INFORMATIKA', 'ENGLISH_EDUCATION', 'UMUM')),
    campus_template_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'IN_PROGRESS',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabel Metadata Rujukan & Sitasi (Grounding Data)
CREATE TABLE citations (
    citation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID REFERENCES theses(thesis_id) ON DELETE CASCADE,
    doi VARCHAR(255),
    title TEXT NOT NULL,
    authors TEXT[] NOT NULL,
    publication_year INT NOT NULL,
    journal_name VARCHAR(255),
    volume_issue VARCHAR(100),
    page_range VARCHAR(50),
    pdf_url TEXT,
    highlighted_snippet TEXT NOT NULL,
    page_number INT NOT NULL,
    source_database VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabel Bagian Naskah per Sub-Bab
CREATE TABLE thesis_sections (
    section_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID REFERENCES theses(thesis_id) ON DELETE CASCADE,
    chapter_code VARCHAR(20) NOT NULL,
    section_code VARCHAR(20) NOT NULL,
    section_title VARCHAR(255) NOT NULL,
    content_markdown TEXT NOT NULL,
    word_count INT DEFAULT 0,
    version_number INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Tech Stack & Arsitektur Infrastruktur

Tabel berikut memperincikan komponen teknologi yang digunakan pada setiap lapisan sistem (*layer*).

| Lapisan Sistem | Teknologi / Framework | Fungsi Utama |
| --- | --- | --- |
| **Frontend UI/UX** | Next.js 15 (React 19, TypeScript, Tailwind CSS, Shadcn UI) | Antarmuka pengguna responsif, TipTap WYSIWYG editor, dan rendering PDF viewer. |
| **PDF Reader & Highlight** | `@react-pdf-viewer/core` + Custom Canvas Overlay | Menampilkan PDF rujukan asli dan menggambar kotak stabilo kuning (*bounding box highlight*). |
| **Backend Framework** | Python 3.12 + FastAPI | *API Gateway*, manajemen autentikasi, serta pemrosesan dokumen asynchronous. |
| **Agent Orchestration** | LangGraph / CrewAI | Mengelola alur kerja sekuensial *multi-agent*, penguncian memori konteks, serta penanganan revisi. |
| **AI Inference Engine** | **NVIDIA NIM (NVIDIA Inference Microservices)** | Mikroservis inferensi LLM berkecepatan tinggi berbasis TensorRT-LLM (menggunakan model Llama 3.3 70B, DeepSeek-R1/V3, atau Nemotron 3.5). |
| **Vector Database (RAG)** | FAISS / Qdrant | Penyimpanan dan pencarian *vector embedding* segmen artikel ilmiah secara cepat. |
| **Document Export Engine** | `python-docx` + `pypdf` | Generator dokumen Microsoft Word (DOCX) berformat presisi tinggi sesuai margin dan spasi kampus. |
| **Visualizer Rendering** | `plotly`, `matplotlib`, & `kroki.io` API | Rendering grafik statistik kuantitatif serta diagram PlantUML/MermaidJS. |

---

## 7. Alur Aplikasi (App Flow & Wireframe Step-by-Step)

Alur kerja pengguna di dalam aplikasi dirancang intuitif dalam 6 langkah utama:

1. **Langkah 1: Pengisian Formulir Inisiasi (Promptless UI)**
   Pengguna memilih Jurusan (*Informatika / Pendidikan Bahasa Inggris / Umum*), memilih templat kampus (pilihan dari daftar preset atau mengunggah PDF pedoman skripsi), serta menginput ide topik kasar.
2. **Langkah 2: Pemilihan Judul & Matriks Variabel**
   Sistem menampilkan 5 opsi rekomendasi judul skripsi beserta analisis celah penelitian (*research gap*). Pengguna memilih satu judul yang disetujui.
3. **Langkah 3: Penarikan & Verifikasi Rujukan (RAG Search)**
   Agen Literatur menarik 10 hingga 15 artikel jurnal ilmiah yang relevan dari OpenAlex/Crossref. Pengguna dapat meninjau abstrak dan kepastian DOI jurnal tersebut.
4. **Langkah 4: Generasi Draf Bertahap (Per Sub-Bab)**
   Sistem melakukan generasi draf per sub-bab secara sekuensial. Layar menampilkan antarmuka *split-screen*: Draf Tulisan di sisi kiri dan Panel Highlight Kutipan Visual di sisi kanan.
5. **Langkah 5: Pengayaan Visual Data & Diagram**
   Sistem secara otomatis menyisipkan tabel statistik dan grafik (Kuantitatif) atau diagram alur pemikiran/UML PlantUML (Kualitatif/Informatika) pada Bab 4.
6. **Langkah 6: Review Multi-Agent & Ekspor Dokumen**
   Agen Dosen Penguji menyajikan daftar simulasi pertanyaan sidang. Agen Guardrail memverifikasi ketercapaian target kata dan keaktifan tautan DOI. Pengguna mengekspor draf final ke format `.docx`.

---

## 8. Persyaratan Non-Fungsional, Keamanan, & Etika Akademik

* **Pencegahan Halusinasi Sitasi (Grounding Enforcement)**: Setiap draf teks yang dibuat diwajibkan melewati filter validasi RAG. Klaim faktual yang tidak memiliki rujukan DOI aktif dari database ilmiah secara otomatis ditolak oleh *Quality Guardrail Agent*.
* **Kecepatan Inferensi (*Low Latency*)**: Pemanfaatan mikroservis **NVIDIA NIM** menjamin waktu generasi per sub-bab selesai dalam waktu kurang dari 15 detik, mencegah kondisi antarmuka membeku (*freeze*).
* **Etika Akademik & Transparansi**: Platform menyertakan *disclaimer* resmi bahwa draf tulisan yang dihasilkan berfungsi sebagai bahan asistensi draf awal dan media bimbingan, bukan untuk tindakan joki skripsi. Pengguna diimbau untuk selalu melakukan penulisan ulang (*paraphrasing*) menggunakan pemikiran kritis mandiri.
* **Keamanan Data Pengguna**: Draf naskah dan dokumen yang diunggah disimpan dengan enkripsi *AES-256 at rest* serta tidak digunakan untuk pelatihan model publik.

---

## 9. Roadmap Pengembangan Produk

Tabel berikut merangkum empat fase rencana eksekusi pengembangan produk dari tahap MVP hingga rilis penuh.

| Fase Pengembangan | Durasi Pengerjaan | Target Luaran Utama |
| --- | --- | --- |
| **Fase 1: Core Engine & MVP** | Minggu 1 – 4 | Formulir *Promptless*, *Backend Prompt Orchestrator*, Core Multi-Agent (*Writer & Advisor*), Integrasi API OpenAlex/Crossref, Templat Standar 5 Bab. |
| **Fase 2: Visual Highlight & RAG** | Minggu 5 – 6 | Antarmuka *split-screen* PDF Reader Viewer dengan *Yellow Highlighter*, Generator Daftar Pustaka Otomatis (APA 7th & IEEE). |
| **Fase 3: Dynamic Campus Parser** | Minggu 7 – 8 | Engine Parser PDF Pedoman Kampus ke JSON, Modul Visualisasi Grafik Kuantitatif (Plotly) & Diagram PlantUML. |
| **Fase 4: Multi-Agent Polish & Release** | Minggu 9 – 10 | Integrasi *Examiner Agent* (Simulasi Pertanyaan Sidang), Ekspor DOCX Berpresisi Tinggi, & Pengujian Terbuka (*Beta Testing*) Dual-Domain. |
