"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import type { SharedThesis } from "@/lib/types";
import { BookMarked, Loader2, MessageSquarePlus } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const NAME_KEY = "skripsi-ai-pembimbing";

/** Halaman baca-saja untuk dosen pembimbing: tanpa akun, hanya baca dan komentar per subbab. */
export default function BimbinganPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<SharedThesis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [author, setAuthor] = useState("");
  const [draft, setDraft] = useState<{ code: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api.readShared(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tautan tidak dapat dibuka");
    }
  }, [token]);

  useEffect(() => {
    void load();
    try {
      setAuthor(localStorage.getItem(NAME_KEY) ?? "");
    } catch {
      /* penyimpanan diblokir */
    }
  }, [load]);

  const send = async () => {
    if (!draft || draft.text.trim().length < 2) return;
    setBusy(true);
    try {
      try {
        localStorage.setItem(NAME_KEY, author);
      } catch {
        /* abaikan */
      }
      await api.addSharedComment(token, { section_code: draft.code, author: author.trim() || "Pembimbing", text: draft.text.trim() });
      setDraft(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Komentar gagal dikirim");
    } finally {
      setBusy(false);
    }
  };

  if (error && !data) {
    return (
      <main className="mx-auto grid min-h-dvh max-w-md place-items-center px-4">
        <Card className="text-center">
          <h1 className="t-heading-sm">Tautan tidak dapat dibuka</h1>
          <p className="mt-2 text-[13px] text-black/60">{error}. Minta mahasiswa membuat tautan baru.</p>
        </Card>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="grid min-h-dvh place-items-center text-[13px] text-black/50">
        <span className="inline-flex items-center gap-2">
          <Loader2 size={16} className="animate-spin" /> Memuat…
        </span>
      </main>
    );
  }

  return (
    <div className="safe-top min-h-dvh">
      <header className="border-b border-hairline bg-canvas/85 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-btn bg-brand text-white">
            <BookMarked size={17} />
          </span>
          <span className="font-bold tracking-tight">Skripsa</span>
          <Pill className="ml-auto">Mode pembimbing · baca dan komentar</Pill>
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-5 px-4 pb-24 pt-6">
        <div>
          <h1 className="t-heading">{data.title}</h1>
          {data.author && <p className="mt-1 text-[13px] text-black/55">Penulis: {data.author}</p>}
        </div>

        <Card>
          <label htmlFor="who" className="mb-1.5 block text-sm font-medium">
            Nama Anda (tampil pada komentar)
          </label>
          <Input id="who" value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Mis. Dr. Ani Wijaya, M.Kom." maxLength={80} />
        </Card>

        {data.sections.length === 0 && <p className="text-[13px] text-black/50">Belum ada subbab yang ditulis.</p>}
        {data.sections.map((s) => {
          const mine = data.comments.filter((c) => c.sectionCode === s.code);
          return (
            <Card key={s.code}>
              <h2 className="font-semibold">
                {s.code} {s.title}
              </h2>
              <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-charcoal">
                {s.content.split(/\n+/).map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>
              {mine.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {mine.map((c) => (
                    <li key={c.id} className={`rounded-btn border p-2.5 text-[13px] ${c.resolved ? "border-hairline text-black/40" : "border-saffron/40 bg-saffron/5"}`}>
                      <strong>{c.author}</strong>: {c.text} {c.resolved && <span className="text-black/40">· selesai</span>}
                    </li>
                  ))}
                </ul>
              )}
              {draft?.code === s.code ? (
                <div className="mt-3 space-y-2">
                  <Textarea rows={3} autoFocus value={draft.text} onChange={(e) => setDraft({ code: s.code, text: e.target.value })} placeholder="Tulis komentar untuk subbab ini" maxLength={1500} />
                  <div className="flex gap-2">
                    <Button onClick={send} loading={busy} disabled={draft.text.trim().length < 2}>
                      Kirim komentar
                    </Button>
                    <Button variant="text" onClick={() => setDraft(null)}>
                      Batal
                    </Button>
                  </div>
                </div>
              ) : (
                <Button className="mt-3" variant="ghost" size="sm" onClick={() => setDraft({ code: s.code, text: "" })}>
                  <MessageSquarePlus size={14} /> Beri komentar
                </Button>
              )}
            </Card>
          );
        })}

        {data.bibliography.length > 0 && (
          <Card>
            <h2 className="font-semibold">Daftar pustaka</h2>
            <ul className="mt-3 space-y-2 text-[13.5px] leading-relaxed text-black/75">
              {data.bibliography.map((b, i) => (
                <li key={i} className="pl-6 -indent-6">
                  {b}
                </li>
              ))}
            </ul>
          </Card>
        )}
        {error && <p className="text-[13px] text-vermillion">{error}</p>}
      </main>
    </div>
  );
}
