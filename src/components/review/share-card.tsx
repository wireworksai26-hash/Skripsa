"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { ShareComment } from "@/lib/types";
import { Check, Copy, Link2, Unlink } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/** Tautan baca-saja untuk dosen pembimbing + komentar yang masuk. Mencabut tautan langsung mematikannya. */
export function ShareCard() {
  const project = useProject((s) => s.project);
  const setPart = useProject((s) => s.setPart);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comments, setComments] = useState<ShareComment[]>([]);
  const id = project?.id;
  const token = project?.shareToken ?? null;

  const refresh = useCallback(async () => {
    if (!id) return;
    try {
      setComments(await api.listComments(id));
    } catch {
      /* komentar tidak kritis */
    }
  }, [id]);
  useEffect(() => {
    void refresh();
  }, [refresh, token]);

  if (!project) return null;
  const url = token && typeof window !== "undefined" ? `${window.location.origin}/bimbingan/${token}` : "";

  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal");
    } finally {
      setBusy(false);
    }
  };

  const open = comments.filter((c) => !c.resolved);
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">
          <Link2 size={12} /> Bimbingan
        </Pill>
        {token ? <Pill tone="green">Tautan aktif</Pill> : <Pill>Belum dibagikan</Pill>}
        {open.length > 0 && <Pill tone="yellow">{open.length} komentar baru</Pill>}
      </div>
      <h2 className="t-heading-sm mt-3">Bagikan ke dosen pembimbing</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">
        Pembimbing membuka draf lewat tautan tanpa akun, hanya bisa membaca dan memberi komentar per subbab. Siapa pun yang memegang tautan bisa membukanya, jadi cabut bila sudah tidak perlu.
      </p>

      {!token ? (
        <Button className="mt-4" loading={busy} onClick={() => act(async () => setPart({ shareToken: await api.createShare(project.id) }))}>
          {!busy && <Link2 size={15} />} Buat tautan
        </Button>
      ) : (
        <div className="mt-4 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row">
            <input readOnly value={url} aria-label="Tautan bimbingan" className="min-h-11 w-full rounded-btn border border-hairline bg-canvas px-3 text-[14px]" onFocus={(e) => e.currentTarget.select()} />
            <Button
              variant="ghost"
              onClick={async () => {
                await navigator.clipboard.writeText(url).catch(() => undefined);
                setCopied(true);
                setTimeout(() => setCopied(false), 1800);
              }}
            >
              {copied ? <Check size={15} /> : <Copy size={15} />} {copied ? "Tersalin" : "Salin"}
            </Button>
            <Button variant="danger" loading={busy} onClick={() => act(async () => (await api.revokeShare(project.id), setPart({ shareToken: null })))}>
              {!busy && <Unlink size={15} />} Cabut
            </Button>
          </div>
        </div>
      )}
      {error && <p className="mt-3 text-[13px] text-vermillion">{error}</p>}

      {comments.length > 0 && (
        <ul className="mt-5 space-y-2">
          {comments.map((c) => (
            <li key={c.id} className={`rounded-btn border p-3 text-[13.5px] ${c.resolved ? "border-hairline bg-black/[0.02] text-black/45" : "border-saffron/40 bg-saffron/5"}`}>
              <p className="flex flex-wrap items-center gap-2 text-[12px] text-black/50">
                <strong className="text-black/75">{c.author}</strong>
                {c.sectionCode && <span>· subbab {c.sectionCode}</span>}
                <span>· {new Date(c.createdAt).toLocaleDateString("id-ID", { day: "numeric", month: "short" })}</span>
              </p>
              <p className="mt-1 whitespace-pre-line">{c.text}</p>
              <button
                className="mt-1.5 min-h-8 text-[12.5px] font-medium text-brand underline underline-offset-2"
                onClick={() => act(async () => (await api.resolveComment(project.id, c.id, !c.resolved), await refresh()))}
              >
                {c.resolved ? "Buka lagi" : "Tandai selesai"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
