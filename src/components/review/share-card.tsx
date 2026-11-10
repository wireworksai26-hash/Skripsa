"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { askConfirm } from "@/components/ui/confirm";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useProject } from "@/lib/store";
import type { ShareComment } from "@/lib/types";
import { Check, Copy, Link2, Undo2, Unlink, Wand2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/** Tautan baca-saja untuk dosen pembimbing + komentar yang masuk. Mencabut tautan langsung mematikannya. */
export function ShareCard() {
  const project = useProject((s) => s.project);
  const setPart = useProject((s) => s.setPart);
  const reviseSection = useProject((s) => s.reviseSection);
  const undoSection = useProject((s) => s.undoSection);
  const [applied, setApplied] = useState<Record<string, string>>({});
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
  const known = new Set(project.sections.map((s) => s.sectionCode));
  // Komentar terbuka dikelompokkan per subbab; yang tanpa subbab tidak bisa diterapkan otomatis.
  const bySection = open.reduce<Record<string, ShareComment[]>>((acc, c) => {
    if (c.sectionCode && known.has(c.sectionCode)) (acc[c.sectionCode] ??= []).push(c);
    return acc;
  }, {});

  const apply = async (code: string) => {
    const group = bySection[code];
    const sec = project.sections.find((x) => x.sectionCode === code);
    if (!group || !sec) return;
    const imported = sec.origin === "IMPORTED";
    if (imported && !(await askConfirm(`Subbab ${code} adalah tulisan Anda. Agen akan menulis ulang sesuai komentar pembimbing; versi lama disimpan dan bisa diurungkan.`, { title: "Ubah tulisan Anda?", confirmLabel: "Terapkan" }))) return;
    await act(async () => {
      const r = await reviseSection(code, group.map((c) => `Komentar pembimbing${c.author ? ` (${c.author})` : ""}: ${c.text}`), imported);
      await Promise.all(group.map((c) => api.resolveComment(project.id, c.id, true)));
      setApplied((a) => ({ ...a, [code]: `${r.changes.length > 0 ? r.changes.join("; ") : "Subbab diperbaiki"} (${r.provider})` }));
      await refresh();
    });
  };
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

      {Object.keys(bySection).length > 0 && (
        <div className="mt-5 rounded-card border border-saffron/40 bg-saffron/5 p-3">
          <p className="text-[13.5px] font-semibold">Tugas revisi dari pembimbing</p>
          <p className="mt-0.5 text-[12px] text-black/55">Agen menulis ulang subbab sesuai komentar, bersandar pada rujukan yang sudah Anda pilih. Versi lama tersimpan dan bisa diurungkan.</p>
          <ul className="mt-2 space-y-2">
            {Object.entries(bySection).map(([code, group]) => (
              <li key={code} className="text-[13px]">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="min-w-0 flex-1">
                    <strong>Subbab {code}</strong> · {group.length} komentar
                  </span>
                  <Button size="sm" onClick={() => apply(code)} disabled={busy} loading={busy}>
                    {!busy && <Wand2 size={13} />} Terapkan
                  </Button>
                  {applied[code] && (
                    <Button size="sm" variant="text" onClick={() => act(async () => (await undoSection(code), setApplied((a) => { const n = { ...a }; delete n[code]; return n; })))}>
                      <Undo2 size={13} /> Urungkan
                    </Button>
                  )}
                </div>
                {applied[code] && <p className="mt-1 text-[12px] text-black/55">{applied[code]}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

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
