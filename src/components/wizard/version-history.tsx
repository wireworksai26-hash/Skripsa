"use client";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { SectionVersionInfo } from "@/lib/types";
import { History } from "lucide-react";
import { useState } from "react";

type Op = { t: "same" | "add" | "del"; w: string };

/** Diff per kata (LCS). Teks panjang dipotong agar tetap cepat di ponsel. */
export function wordDiff(a: string, b: string, cap = 1400): Op[] {
  const x = a.split(/\s+/).filter(Boolean).slice(0, cap);
  const y = b.split(/\s+/).filter(Boolean).slice(0, cap);
  const n = x.length;
  const m = y.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = x[i] === y[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: Op[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (x[i] === y[j]) {
      out.push({ t: "same", w: x[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ t: "del", w: x[i++] });
    else out.push({ t: "add", w: y[j++] });
  }
  while (i < n) out.push({ t: "del", w: x[i++] });
  while (j < m) out.push({ t: "add", w: y[j++] });
  return out;
}

/** Riwayat versi satu subbab dengan perbandingan terhadap isi sekarang. */
export function VersionHistory({ thesisId, code, current }: { thesisId: string; code: string; current: string }) {
  const [versions, setVersions] = useState<SectionVersionInfo[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setVersions(await api.sectionVersions(thesisId, code));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal memuat riwayat");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 border-t border-hairline pt-3">
      <Button variant="text" size="sm" onClick={load} loading={busy}>
        {!busy && <History size={14} />} Riwayat versi
      </Button>
      {error && <p className="text-[12px] text-vermillion">{error}</p>}
      {versions && versions.length === 0 && <p className="mt-1 text-[12px] text-black/45">Belum ada versi sebelumnya. Versi tersimpan otomatis saat subbab dibuat ulang atau diperbaiki.</p>}
      {versions?.map((v) => (
        <div key={v.id} className="mt-2">
          <button className="min-h-9 text-left text-[12.5px] text-brand underline underline-offset-2" onClick={() => setOpen(open === v.id ? null : v.id)}>
            {new Date(v.createdAt).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} · {v.reason || "versi"}
          </button>
          {open === v.id && (
            <p className="scroll-thin mt-1 max-h-56 overflow-y-auto rounded-btn border border-hairline p-2.5 text-[13px] leading-relaxed">
              {wordDiff(v.content, current).map((o, k) => (
                <span key={k} className={o.t === "add" ? "rounded-[3px] bg-[#d7f2d9]" : o.t === "del" ? "rounded-[3px] bg-vermillion/15 line-through" : ""}>
                  {o.w}{" "}
                </span>
              ))}
              <span className="mt-2 block text-[11px] text-black/40">Hijau = ada di versi sekarang, merah coret = hanya ada di versi lama.</span>
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
