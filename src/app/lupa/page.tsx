"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { api } from "@/lib/api";
import Link from "next/link";
import { useState } from "react";

export default function LupaPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.forgotPassword(email.trim());
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengirim");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto grid min-h-dvh max-w-md place-items-center px-4 py-10">
      <Card className="w-full">
        <h1 className="t-heading-sm">Lupa password</h1>
        {done ? (
          <p className="mt-3 text-[14px] leading-relaxed text-black/70">Bila email itu terdaftar, tautan untuk mengatur ulang password sudah dikirim. Tautan berlaku 30 menit.</p>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-4">
            <div>
              <Label htmlFor="email">Email akun</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </div>
            {error && <p className="text-[13px] text-vermillion">{error}</p>}
            <Button type="submit" className="w-full" loading={busy} disabled={busy || !email.includes("@")}>
              Kirim tautan
            </Button>
          </form>
        )}
        <Link href="/masuk" className="mt-4 inline-block text-[13px] font-medium text-brand underline underline-offset-2">
          Kembali ke halaman masuk
        </Link>
      </Card>
    </main>
  );
}
