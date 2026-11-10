// Dijalankan sebelum `next build`. NEXT_PUBLIC_* ikut tertanam saat build, jadi salah isi baru ketahuan setelah deploy.
// Mode satu service memakai alamat API relatif (/api). Alamat absolut hanya sah bila backend sengaja dipisah (HTTPS).
const onRailway = Boolean(process.env.RAILWAY_ENVIRONMENT || process.env.RAILWAY_PROJECT_ID);
const api = process.env.NEXT_PUBLIC_API_URL;

if (onRailway && api !== undefined && api.startsWith("http") && !/^https:\/\//.test(api)) {
  console.error(`\n[Skripsa] NEXT_PUBLIC_API_URL="${api}" harus HTTPS (atau /api untuk mode satu service).\n`);
  process.exit(1);
}
if (onRailway && !process.env.NEXT_PUBLIC_ONESIGNAL_APP_ID) {
  console.warn("[Skripsa] NEXT_PUBLIC_ONESIGNAL_APP_ID kosong: tombol notifikasi akan nonaktif (tidak menggagalkan build).");
}
