// Mode satu service (Railway): browser hanya bicara ke domain ini. Semua panggilan /api/* diteruskan Next.js
// ke backend FastAPI yang berjalan di container yang sama (127.0.0.1:8000), jadi tidak ada CORS.
// Di pengembangan, NEXT_PUBLIC_API_URL kosong -> frontend memanggil http://localhost:8000 langsung.
const internalApi = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

const apiOrigin = (() => {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (raw === undefined) return "http://localhost:8000";
  if (!/^https?:\/\//.test(raw)) return null; // alamat relatif (/api) = same-origin, tercakup 'self'
  try {
    return new URL(raw).origin;
  } catch {
    return null;
  }
})();

const isDev = process.env.NODE_ENV !== "production";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} https://cdn.onesignal.com https://*.onesignal.com`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://cdn.onesignal.com https://*.onesignal.com",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin ? apiOrigin + " " : ""}ws: wss: https://kroki.io https://api.onesignal.com https://onesignal.com https://*.onesignal.com`,
  "worker-src 'self' blob:",
  "media-src 'self' blob:",
  "frame-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  // Memungkinkan build/uji terpisah (NEXT_DIST_DIR=.next-test) tanpa menimpa server `next dev` yang sedang berjalan.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Panggilan LLM bisa memakan beberapa menit; bawaan proxy Next memutus lebih cepat.
  experimental: { proxyTimeout: 300_000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${internalApi}/:path*` }];
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
