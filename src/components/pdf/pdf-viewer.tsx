"use client";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { bestMatch } from "@/lib/pdf-highlight";
import { ExternalLink, FileSearch, Highlighter, Loader2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface Props {
  thesisId: string;
  citationId: string;
  title: string;
  /** Kalimat rujukan yang menjadi dasar klaim; inilah yang disorot kuning. */
  snippet: string;
  externalUrl?: string;
  /** false bila rujukan tak punya tautan teks penuh: tidak ada permintaan ke server. */
  hasPdf?: boolean;
  onClose: () => void;
}

type PdfItem = { str: string; transform: number[]; width: number; height: number };

const MAX_PAGES = 40;

export function PdfViewer({ thesisId, citationId, title, snippet, externalUrl, hasPdf = true, onClose }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [pages, setPages] = useState(0);
  const [match, setMatch] = useState<{ page: number; coverage: number } | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    let destroy: (() => void) | null = null;
    const host = scroller.current;
    setStatus("loading");
    setError(null);
    setMatch(undefined);
    if (host) host.replaceChildren();

    if (!hasPdf) {
      setError("Rujukan ini tidak punya tautan teks penuh di basis data. Kalimat rujukan diambil dari abstrak; periksa naskahnya lewat DOI.");
      setStatus("error");
      return;
    }

    (async () => {
      const buf = await api.fetchCitationPdf(thesisId, citationId);
      const pdfjs = await import("pdfjs-dist");
      pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
      const task = pdfjs.getDocument({ data: new Uint8Array(buf) });
      destroy = () => void task.destroy();
      const doc = await task.promise;
      if (cancelled || !host) return;

      const total = Math.min(doc.numPages, MAX_PAGES);
      setPages(doc.numPages);
      const width = Math.max(320, host.clientWidth - 24);

      // 1) teks semua halaman dulu: pencocokan stabilo butuh seluruh dokumen sebelum menggambar
      const loaded = [];
      for (let p = 1; p <= total; p++) {
        const page = await doc.getPage(p);
        const base = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: Math.min(2, Math.max(0.6, width / base.width)) });
        const content = await page.getTextContent();
        const items = content.items.filter((i): i is typeof i & PdfItem => "str" in i) as unknown as PdfItem[];
        loaded.push({ page, viewport, items });
      }
      if (cancelled) return;

      const found = snippet.trim() ? bestMatch(loaded.map((l) => l.items), snippet) : null;
      setMatch(found ? { page: found.page, coverage: found.coverage } : null);

      // 2) kerangka halaman ber-ukuran pasti, lalu loncat ke halaman cocok sebelum kanvas selesai digambar
      const dpr = window.devicePixelRatio || 1;
      const frames = loaded.map(({ viewport, items }, idx) => {
        const wrap = document.createElement("div");
        wrap.style.cssText = `position:relative;margin:0 auto 12px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.15);width:${viewport.width}px;height:${viewport.height}px`;
        wrap.dataset.page = String(idx + 1);
        const canvas = document.createElement("canvas");
        canvas.width = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);
        canvas.style.cssText = `width:${viewport.width}px;height:${viewport.height}px;display:block`;
        wrap.appendChild(canvas);

        let firstTop: number | null = null;
        if (found && found.page === idx + 1) {
          for (const span of found.spans) {
            const item = items[span.item];
            const t = pdfjs.Util.transform(viewport.transform, item.transform);
            const fontH = Math.hypot(t[2], t[3]) || item.height * viewport.scale;
            const w = item.width * viewport.scale;
            const mark = document.createElement("div");
            const top = t[5] - fontH * 0.9;
            mark.style.cssText = `position:absolute;left:${t[4] + w * span.from}px;top:${top}px;width:${w * (span.to - span.from)}px;height:${fontH * 1.2}px;background:rgba(255,226,0,.45);mix-blend-mode:multiply;border-radius:2px;pointer-events:none`;
            wrap.appendChild(mark);
            if (firstTop === null || top < firstTop) firstTop = top;
          }
        }
        host.appendChild(wrap);
        return { wrap, canvas, firstTop };
      });
      setStatus("ready");

      if (found) {
        const f = frames[found.page - 1];
        host.scrollTo({ top: f.wrap.offsetTop + (f.firstTop ?? 0) - 90 });
      }

      // 3) gambar halaman cocok lebih dulu, sisanya berurutan
      const order = loaded.map((_, i) => i);
      if (found) order.sort((a, b) => Number(b === found.page - 1) - Number(a === found.page - 1) || a - b);
      for (const i of order) {
        if (cancelled) return;
        const { page, viewport } = loaded[i];
        const { canvas } = frames[i];
        const ctx = canvas.getContext("2d");
        if (!ctx) continue;
        await page.render({ canvas, canvasContext: ctx, viewport, transform: [dpr, 0, 0, dpr, 0, 0] }).promise;
      }
    })().catch((e) => {
      if (cancelled) return;
      setError(e instanceof Error ? e.message : "PDF tidak dapat ditampilkan");
      setStatus("error");
    });

    return () => {
      cancelled = true;
      destroy?.();
    };
  }, [thesisId, citationId, snippet, hasPdf]);

  return (
    <div className="flex h-full min-h-0 flex-col rounded-card border border-hairline bg-white">
      <div className="flex items-start justify-between gap-3 border-b border-hairline p-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[12px] font-semibold text-black/80">
            <Highlighter size={14} className="text-saffron" /> Pembaca PDF · stabilo kuning
          </p>
          <p className="mt-0.5 line-clamp-2 text-[12px] text-black/55">{title}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {externalUrl && (
            <a
              href={externalUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-btn p-2 text-black/55 hover:bg-black/5"
              aria-label="Buka PDF di tab baru"
            >
              <ExternalLink size={15} />
            </a>
          )}
          <Button variant="text" size="sm" onClick={onClose} aria-label="Tutup pembaca PDF">
            <X size={16} />
          </Button>
        </div>
      </div>

      <div className="border-b border-hairline bg-canvas px-3 py-2 text-[12px]">
        {status === "loading" && (
          <span className="inline-flex items-center gap-2 text-black/55">
            <Loader2 size={13} className="animate-spin" /> Mengunduh dan membaca PDF…
          </span>
        )}
        {status === "ready" && match && (
          <span className="text-black/70">
            Kalimat rujukan ditemukan di <strong>halaman {match.page}</strong> (kecocokan {Math.round(match.coverage * 100)}%) · {pages} halaman
          </span>
        )}
        {status === "ready" && match === null && (
          <span className="inline-flex items-start gap-1.5 text-vermillion">
            <FileSearch size={13} className="mt-0.5 shrink-0" />
            Kalimat rujukan tidak ditemukan pada PDF (abstrak bisa berbeda dari naskah). Periksa manual di dokumen ini.
          </span>
        )}
        {status === "error" && <span className="text-vermillion">{error}</span>}
      </div>

      {status === "error" && snippet && (
        <div className="border-b border-hairline p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-black/40">Kalimat rujukan (dari abstrak)</p>
          <p className="mt-1 rounded-[4px] bg-marigold/35 p-2 text-[12.5px] leading-relaxed text-black/85">{snippet}</p>
        </div>
      )}

      <div ref={scroller} className="relative min-h-0 flex-1 overflow-y-auto bg-black/[0.04] p-3" />
    </div>
  );
}
