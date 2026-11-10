# Deploy ke Railway (satu service + Postgres)

Hasil akhir: **satu service** `app` (frontend Next.js dan backend FastAPI dalam satu container) ditambah satu database Postgres, dengan satu domain HTTPS dari Railway. PWA dan push notification membutuhkan HTTPS, dan Railway menyediakannya.

Cara kerjanya: container menjalankan FastAPI di `127.0.0.1:8000` (tidak terbuka ke publik) dan Next.js di port publik. Browser hanya mengenal satu domain; Next.js meneruskan `/api/*` ke backend. Karena same-origin, tidak ada CORS dan tidak ada `NEXT_PUBLIC_API_URL` yang harus diisi.

> Status verifikasi: build produksi, proxy `/api`, CSP, dan pemuatan halaman sudah diuji di mesin pengembangan (backend + Next.js produksi, satu domain). Yang **belum** bisa diuji di sini: build Docker itu sendiri, koneksi ke Postgres sungguhan, email, dan push OneSignal. Bagian "Cek akhir" memeriksa semuanya setelah deploy.

## 0. Persiapan
- Repo di GitHub: `wireworksai26-hash/Skripsa`.
- Buat kunci rahasia login (simpan, jangan di-commit):
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- Siapkan kunci API: NVIDIA NIM (wajib untuk menulis draf), Groq, Gemini, OpenAlex.

## 1. Project dan database
1. Railway > **New Project** > **Deploy from GitHub repo** > pilih `Skripsa`. Service ini otomatis memakai `Dockerfile` dan `railway.json` di akar repo. **Root Directory dibiarkan kosong.**
2. Di project yang sama: **+ New** > **Database** > **PostgreSQL**. Jangan pakai SQLite, disk Railway hilang saat redeploy.

## 2. Variabel service `app`
Di **Variables**, isi:

| Variabel | Nilai |
|---|---|
| `SKRIPSI_ENVIRONMENT` | `production` |
| `SKRIPSI_SECRET_KEY` | kunci acak dari langkah 0 |
| `SKRIPSI_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `SKRIPSI_NIM_API_KEY` | kunci NVIDIA NIM |
| `SKRIPSI_GROQ_API_KEY`, `SKRIPSI_GEMINI_API_KEY` | kunci LLM cadangan |
| `SKRIPSI_OPENALEX_API_KEY` | kunci OpenAlex |
| `SKRIPSI_POLITE_EMAIL` | email nyata Anda (Crossref/Unpaywall) |
| `SKRIPSI_APP_URL` | `https://<domain-app>` (isi setelah langkah 3) |
| `NEXT_PUBLIC_ONESIGNAL_APP_ID` | App ID OneSignal (langkah 4; dibaca saat build) |
| `SKRIPSI_ONESIGNAL_APP_ID`, `SKRIPSI_ONESIGNAL_API_KEY` | dari OneSignal (langkah 4) |

Opsional: `SKRIPSI_CORE_API_KEY`, `SKRIPSI_SEMANTIC_SCHOLAR_API_KEY`. Untuk lupa password dan verifikasi email: `SKRIPSI_SMTP_HOST`, `SKRIPSI_SMTP_PORT`, `SKRIPSI_SMTP_USER`, `SKRIPSI_SMTP_PASSWORD`, `SKRIPSI_SMTP_FROM`. `SKRIPSI_CORS_ORIGINS` **tidak perlu**.

## 3. Domain
**Settings** > **Networking** > **Generate Domain**, lalu isi `SKRIPSI_APP_URL` dengan `https://<domain>` tersebut. Cek `https://<domain>/api/healthz`, harus `{"status":"ok"}`. Domain sendiri: **Custom Domain**, lalu perbarui `SKRIPSI_APP_URL` dan Site URL OneSignal.

## 4. OneSignal
1. OneSignal > **New App/Website** > **Web** > **Typical Site**. **Site URL** = `https://<domain>` tanpa garis miring akhir.
2. **Service worker path** = `sw.js`, **scope** = `/`. Jangan mengunggah berkas worker OneSignal terpisah; `public/sw.js` sudah memuat SDK lewat `importScripts`.
3. App ID ke `NEXT_PUBLIC_ONESIGNAL_APP_ID` dan `SKRIPSI_ONESIGNAL_APP_ID`. REST API Key ke `SKRIPSI_ONESIGNAL_API_KEY` (hanya backend).
4. **Redeploy** (App ID frontend ditanam saat build). Buka situs, masuk, `/profil` > **Aktifkan notifikasi**.

iPhone/iPad hanya menerima push setelah situs dipasang ke Layar Utama.

## 5. Perilaku produksi
- `SKRIPSI_ENVIRONMENT=production` mematikan `/api/docs` dan mewajibkan secret key. Backend gagal start dengan pesan jelas bila kosong.
- Satu proses backend; pembatas laju disimpan di memori. Jangan naikkan jumlah replika tanpa memindahkannya ke Redis.
- Bila salah satu proses (backend atau Next.js) berhenti, container ikut berhenti dan Railway memulainya ulang.
- Tabel dan kolom baru dibuat otomatis saat start. PDF pedoman, logo, dan data penelitian tersimpan di Postgres, tanpa volume.
- Panggilan LLM yang lama diteruskan proxy dengan batas waktu 5 menit.

## 6. Cek akhir
1. `https://<domain>/api/healthz` mengembalikan `{"status":"ok"}`.
2. Buka `https://<domain>`, daftar akun, isi profil, buat proyek.
3. DevTools > Application: service worker `sw.js` aktif; Console tanpa galat CSP.
4. Langkah 3 (Rujukan): pencarian mengembalikan hasil; Langkah 4: buat satu subbab.
5. `/profil` > Aktifkan notifikasi; selesaikan review dan pastikan notifikasi tiba.
6. DevTools > Network > Offline, muat ulang: halaman "Anda sedang offline" tampil.

## Masalah umum
| Gejala | Penyebab | Perbaikan |
|---|---|---|
| Build gagal `npm error EBUSY ... node_modules/.cache` | Konfigurasi lama (Nixpacks, `npm ci && npm run build`) | Pakai `railway.json` terbaru (builder Dockerfile); pastikan commit terbaru sudah ter-deploy |
| Healthcheck gagal di awal | Backend butuh beberapa detik menyiapkan tabel | Biarkan; batas waktu 180 detik. Bila tetap gagal, lihat log baris `uvicorn` |
| Crash: `SKRIPSI_SECRET_KEY wajib` | Secret kosong di produksi | Isi kunci acak minimal 32 karakter |
| Semua pengguna kena "Terlalu banyak permintaan" | IP klien tidak terbaca | Pastikan Dockerfile terbaru dipakai (`--proxy-headers`) |
| Tombol notifikasi nonaktif | `NEXT_PUBLIC_ONESIGNAL_APP_ID` kosong saat build | Isi, lalu **Redeploy** |
| Notifikasi tidak tiba | Site URL OneSignal beda dari domain, atau REST key salah | Samakan, cek log baris `push` |
| Data hilang setelah redeploy | Backend memakai SQLite | Pastikan `SKRIPSI_DATABASE_URL` menunjuk ke Postgres |

## Alternatif: dua service terpisah
Dimungkinkan (backend dengan Root Directory `/backend` memakai `backend/Dockerfile`; frontend dengan `NEXT_PUBLIC_API_URL=https://<domain-backend>` dan `SKRIPSI_CORS_ORIGINS=["https://<domain-frontend>"]`), tetapi tidak diperlukan untuk penggunaan biasa.
