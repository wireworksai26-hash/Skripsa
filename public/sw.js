// Satu service worker untuk cache offline dan push OneSignal (scope "/" tidak bisa dipakai dua worker).
try {
  importScripts("https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.sw.js");
} catch (e) {
  // Offline atau diblokir: aplikasi tetap jalan, hanya push yang tidak aktif.
}

const CACHE = "skripsi-pwa-v2";
const PRECACHE = ["/offline.html", "/manifest.json", "/icons/icon-192.png", "/icons/icon-512.png"];
// Di localhost (pengembangan) nama berkas tidak berhash, jadi cache aset akan menyajikan versi basi.
const DEV = ["localhost", "127.0.0.1"].includes(self.location.hostname);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Navigasi: selalu jaringan dulu; bila putus tampilkan halaman offline (bukan halaman lain yang basi).
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline.html")));
    return;
  }

  // Aset berhash Next.js dan ikon: cache-first (produksi saja).
  const immutable = url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/");
  if (DEV || !immutable) return;
  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          }
          return res;
        })
    )
  );
});
