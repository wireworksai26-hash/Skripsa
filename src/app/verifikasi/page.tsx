"use client";

import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function VerifikasiPage() {
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token") ?? "";
    if (!token) {
      setState("error");
      setError("Tautan tidak lengkap.");
      return;
    }
    api
      .verifyEmail(token)
      .then(() => setState("ok"))
      .catch((e) => (setState("error"), setError(e instanceof Error ? e.message : "Verifikasi gagal")));
  }, []);

  return (
    <main className="mx-auto grid min-h-dvh max-w-md place-items-center px-4 py-10">
      <Card className="w-full text-center">
        <h1 className="t-heading-sm">Verifikasi email</h1>
        {state === "loading" && (
          <p className="mt-3 inline-flex items-center gap-2 text-[14px] text-black/60">
            <Loader2 size={15} className="animate-spin" /> Memeriksa tautan…
          </p>
        )}
        {state === "ok" && <p className="mt-3 text-[14px] text-[#0a5f1e]">Email Anda terverifikasi.</p>}
        {state === "error" && <p className="mt-3 text-[14px] text-vermillion">{error}</p>}
        <Link href="/proyek" className="mt-4 inline-block text-[13px] font-medium text-brand underline underline-offset-2">
          Ke aplikasi
        </Link>
      </Card>
    </main>
  );
}
