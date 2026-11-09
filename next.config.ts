import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  // Memungkinkan build/uji terpisah (NEXT_DIST_DIR=.next-test) tanpa menimpa server `next dev` yang sedang berjalan.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
