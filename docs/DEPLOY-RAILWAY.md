# Deploy ke Railway (dengan domain dan OneSignal)

Hasil akhir: dua service di satu project Railway (frontend dan backend) plus satu database Postgres, masing-masing dengan domain HTTPS dari Railway. PWA dan push notification membutuhkan HTTPS, dan Railway menyediakannya.

> Status verifikasi: build produksi frontend, CSP, service worker, dan halaman offline sudah diuji di mesin pengembangan. Yang **belum** bisa diuji di sini: build Docker backend, koneksi ke Postgres sungguhan, pengiriman email, dan push OneSignal. Langkah 7 (cek akhir) memeriksa semuanya setelah deploy.

## 0. Persiapan

- Repo sudah ada di GitHub: `fhmi-kzkf/Skripsa`. Railway men-deploy dari repo itu.
- Buat kunci rahasia untuk login (simpan, jangan di-commit):
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- Siapkan akun OneSignal (langkah 5) dan kunci API: NVIDIA NIM (wajib untuk menulis draf), Groq, Gemini, OpenAlex.

## 1. Buat project dan database

1. Railway > **New Project** > **Deploy from GitHub repo** > pilih `Skripsa`. Hapus service otomatis pertama bila Railway membuatnya; kita buat manual di bawah.
2. Di project: **+ New** > **Database** > **PostgreSQL**. Data jangan disimpan di SQLite karena disk Railway hilang saat redeploy.

## 2. Service backend

1. **+ New** > **GitHub Repo** > `Skripsa`. Beri nama `api`.
2. **Settings** > **Source** > **Root Directory**: `/backend`. Railway otomatis memakai `backend/railway.json` (Dockerfile, health check `/healthz`).
3. **Settings** > **Networking** > **Generate Domain**. Catat, misalnya `https://skripsiai-api.up.railway.app`.
4. **Variables** (isi semuanya, `...` adalah nilai Anda):

| Variabel | Nilai |
|---|---|
| `SKRIPSI_ENVIRONMENT` | `production` (menonaktifkan /docs dan mewajibkan secret key) |
| `SKRIPSI_SECRET_KEY` | kunci acak dari langkah 0 |
| `SKRIPSI_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (referensi ke database) |
| `SKRIPSI_CORS_ORIGINS` | `["https://<domain-frontend>"]` (JSON; isi setelah langkah 3) |
| `SKRIPSI_APP_URL` | `https://<domain-frontend>` |
| `SKRIPSI_NIM_API_KEY` | kunci NVIDIA NIM |
| `SKRIPSI_GROQ_API_KEY`, `SKRIPSI_GEMINI_API_KEY` | kunci LLM cadangan |
| `SKRIPSI_OPENALEX_API_KEY` | kunci OpenAlex |
| `SKRIPSI_POLITE_EMAIL` | email nyata Anda (Crossref/Unpaywall) |
| `SKRIPSI_ONESIGNAL_APP_ID`, `SKRIPSI_ONESIGNAL_API_KEY` | dari OneSignal (langkah 5) |

   Opsional untuk lupa password dan verifikasi email: `SKRIPSI_SMTP_HOST`, `SKRIPSI_SMTP_PORT`, `SKRIPSI_SMTP_USER`, `SKRIPSI_SMTP_PASSWORD`, `SKRIPSI_SMTP_FROM`.

5. Deploy. Cek `https://<domain-backend>/healthz` harus `{"status":"ok"}`.

Backend gagal start dengan pesan jelas bila `SKRIPSI_SECRET_KEY` kosong di produksi. Itu disengaja agar sesi login tidak hilang tiap restart.

## 3. Service frontend

1. **+ New** > **GitHub Repo** > `Skripsa`, beri nama `web`. Root Directory: `/` (kosongkan). Railway memakai `railway.json` di akar.
2. **Variables** (dibaca **saat build**, jadi isi sebelum deploy pertama):

| Variabel | Nilai |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<domain-backend>` dari langkah 2 |
| `NEXT_PUBLIC_ONESIGNAL_APP_ID` | App ID OneSignal (langkah 5) |

   Build gagal dengan pesan jelas bila `NEXT_PUBLIC_API_URL` kosong atau masih localhost.
3. **Generate Domain**, lalu isi balik `SKRIPSI_CORS_ORIGINS` dan `SKRIPSI_APP_URL` di backend dengan domain ini dan redeploy backend.

## 4. Domain sendiri (opsional)

Settings > Networking > **Custom Domain** pada service `web` (dan `api` bila mau), lalu atur CNAME sesuai petunjuk Railway. Setelah domain berubah: perbarui `NEXT_PUBLIC_API_URL` (redeploy `web`), `SKRIPSI_CORS_ORIGINS`, `SKRIPSI_APP_URL`, dan Site URL OneSignal.

## 5. OneSignal

1. Buat app di OneSignal > **New App/Website** > platform **Web**.
2. Pilih **Typical Site**. **Site URL**: domain frontend (`https://<domain-frontend>`), tanpa garis miring akhir.
3. Di pengaturan Web Push:
   - **Service worker path**: `sw.js`
   - **Service worker param/scope**: `/`
   - Jangan mengunggah berkas worker OneSignal terpisah. `public/sw.js` aplikasi sudah memuat SDK OneSignal lewat `importScripts`.
4. Salin **App ID** (publik) ke `NEXT_PUBLIC_ONESIGNAL_APP_ID` (frontend) dan `SKRIPSI_ONESIGNAL_APP_ID` (backend). Salin **REST API Key** ke `SKRIPSI_ONESIGNAL_API_KEY` (backend saja).
5. Redeploy kedua service, buka situs, masuk, lalu di `/profil` tekan **Aktifkan notifikasi**.
6. Uji kirim: selesaikan review di Langkah 6 atau di dashboard OneSignal kirim pesan uji ke pengguna dengan External ID = ID akun Anda.

iPhone/iPad hanya menerima push setelah situs dipasang ke Layar Utama.

## 6. Perilaku produksi yang perlu diketahui

- `SKRIPSI_ENVIRONMENT=production` mematikan dokumentasi API.
- Backend berjalan satu proses; pembatas laju (rate limit) disimpan di memori proses. Jangan naikkan jumlah replika tanpa memindahkan pembatas ke Redis.
- IP klien dibaca dari `X-Forwarded-For` (Dockerfile memakai `--proxy-headers`), jadi pembatas laju bekerja per pengguna, bukan per proxy.
- Basis data dibuat dan kolom baru ditambahkan otomatis saat backend start.
- PDF pedoman, logo, dan data penelitian tersimpan di Postgres. Tidak ada penyimpanan berkas lokal yang perlu dipasangi volume.

## 7. Cek akhir setelah deploy

1. `https://<backend>/healthz` mengembalikan `{"status":"ok"}`.
2. Buka `https://<frontend>`, daftar akun, isi profil, buat proyek.
3. Buka DevTools > Application: service worker `sw.js` aktif, tidak ada galat CSP di Console.
4. Langkah 3 (Rujukan): pencarian mengembalikan hasil; Langkah 4: buat satu subbab.
5. `/profil` > Aktifkan notifikasi > izinkan; selesaikan review dan pastikan notifikasi tiba.
6. Matikan koneksi di DevTools (Offline) lalu muat ulang: halaman "Anda sedang offline" tampil.

## Masalah umum

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| Frontend memuat tetapi semua panggilan gagal / CORS | `SKRIPSI_CORS_ORIGINS` tidak memuat domain frontend persis (https, tanpa `/` akhir) | Perbaiki dan redeploy backend |
| Build frontend gagal soal `NEXT_PUBLIC_API_URL` | Variabel kosong atau localhost | Isi dengan domain backend HTTPS, deploy ulang |
| Backend crash saat start: `SKRIPSI_SECRET_KEY wajib` | Secret tidak diisi di produksi | Isi kunci acak minimal 32 karakter |
| Semua pengguna kena "Terlalu banyak permintaan" | IP proxy dianggap satu klien | Pastikan Dockerfile terbaru yang dipakai (`--proxy-headers`) |
| Tombol notifikasi nonaktif | `NEXT_PUBLIC_ONESIGNAL_APP_ID` kosong saat build | Isi, lalu deploy ulang frontend |
| Notifikasi tidak tiba | Site URL OneSignal berbeda dari domain, atau REST key salah | Samakan, cek log backend baris `push` |
| Data hilang setelah redeploy | Backend memakai SQLite | Pastikan `SKRIPSI_DATABASE_URL` menunjuk ke Postgres |
