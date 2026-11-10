// Dijalankan sebelum `next build`. Variabel NEXT_PUBLIC_* ikut tertanam saat build, jadi salah isi baru ketahuan setelah deploy.
// Di Railway (RAILWAY_ENVIRONMENT terisi) alamat API yang kosong atau localhost menggagalkan build dengan pesan yang jelas.
const onRailway = Boolean(process.env.RAILWAY_ENVIRONMENT || process.env.RAILWAY_PROJECT_ID);
const api = (process.env.NEXT_PUBLIC_API_URL || "").trim();
const bad = !api || /localhost|127\.0\.0\.1/.test(api) || !/^https:\/\//.test(api);

if (onRailway && bad) {
  console.error(
    "\n[Skripsa] NEXT_PUBLIC_API_URL belum benar untuk produksi.\n" +
      `  Nilai sekarang: "${api || "(kosong)"}"\n` +
      "  Isi dengan alamat HTTPS service backend, mis. https://skripsa-api.up.railway.app,\n" +
      "  lalu deploy ulang frontend (variabel NEXT_PUBLIC_* dibaca saat build, bukan saat jalan).\n"
  );
  process.exit(1);
}
if (onRailway && !process.env.NEXT_PUBLIC_ONESIGNAL_APP_ID) {
  console.warn("[Skripsa] NEXT_PUBLIC_ONESIGNAL_APP_ID kosong: tombol notifikasi akan nonaktif (tidak menggagalkan build).");
}
