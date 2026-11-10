import type { Metadata, Viewport } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { ConfirmHost } from "@/components/ui/confirm";
import { OfflineSync } from "@/components/pwa/offline-sync";
import { PushSync } from "@/components/pwa/push-sync";
import { SWRegister } from "@/components/pwa/sw-register";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["400"],
});

export const metadata: Metadata = {
  title: {
    default: "Skripsa — Generator Skripsi Multi-Agent",
    template: "%s · Skripsa",
  },
  description:
    "Platform penulisan skripsi cerdas berarsitektur multi-agent: formulir tanpa prompting, rujukan jurnal nyata (OpenAlex, Crossref, DOAJ, ERIC), verifikasi sitasi, dan review Dosen Pembimbing & Penguji.",
  applicationName: "Skripsa",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "Skripsa",
    statusBarStyle: "default",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f5f4" },
    { media: "(prefers-color-scheme: dark)", color: "#141413" },
  ],
  viewportFit: "cover",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('skripsi-ai-theme');var d=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.dataset.theme=d?'dark':'light';}catch(e){}",
          }}
        />
      </head>
      <body className={`${inter.variable} ${sourceSerif.variable} antialiased`}>
        {children}
        <SWRegister />
        <PushSync />
        <OfflineSync />
        <ConfirmHost />
      </body>
    </html>
  );
}
