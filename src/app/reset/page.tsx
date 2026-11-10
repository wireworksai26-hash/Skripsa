"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { api } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function ResetPage() {
  const [token, setToken] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.resetPassword(token, pw);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengatur ulang");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto grid min-h-dvh max-w-md place-items-center px-4 py-10">
      <Card className="w-full">
        <h1 className="t-heading-sm">Atur ulang password</h1>
        {done ? (
          <p className="mt-3 text-[14px] text-black/70">Password diganti. Silakan masuk dengan password baru.</p>
        ) : !token ? (
          <p className="mt-3 text-[14px] text-vermillion">Tautan tidak lengkap. Minta tautan baru dari halaman lupa password.</p>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-4">
            <div>
              <Label htmlFor="pw">Password baru (min. 8 karakter)</Label>
              <Input id="pw" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
            </div>
            {error && <p className="text-[13px] text-vermillion">{error}</p>}
            <Button type="submit" className="w-full" loading={busy} disabled={busy || pw.length < 8}>
              Simpan password baru
            </Button>
          </form>
        )}
        <Link href="/masuk" className="mt-4 inline-block text-[13px] font-medium text-brand underline underline-offset-2">
          Ke halaman masuk
        </Link>
      </Card>
    </main>
  );
}
