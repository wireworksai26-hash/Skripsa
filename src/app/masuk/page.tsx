"use client";

import { ThemeButton } from "@/components/pwa/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldHint, Input, Label } from "@/components/ui/field";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { BookMarked, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Mode = "masuk" | "daftar";

export default function MasukPage() {
  const router = useRouter();
  const session = useAuth((s) => s.session);
  const ready = useAuth((s) => s.ready);
  const hydrate = useAuth((s) => s.hydrate);
  const signIn = useAuth((s) => s.signIn);

  const [mode, setMode] = useState<Mode>("masuk");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [majorName, setMajorName] = useState("");
  const [campusName, setCampusName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (ready && session) router.replace("/proyek/1-inisiasi");
  }, [ready, session, router]);

  const register = mode === "daftar";
  const valid =
    email.includes("@") &&
    password.length >= (register ? 8 : 1) &&
    (!register || (fullName.trim() && majorName.trim() && campusName.trim()));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const s = register
        ? await api.register({ fullName: fullName.trim(), email: email.trim(), password, majorName: majorName.trim(), campusName: campusName.trim() })
        : await api.login(email.trim(), password);
      signIn(s);
      router.replace("/proyek/1-inisiasi");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal masuk");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto grid min-h-dvh max-w-md place-items-center px-4 py-10">
      <ThemeButton className="fixed right-3 top-3 z-10" />
      <div className="w-full">
        <Link href="/" className="mb-6 flex items-center justify-center gap-2 font-bold">
          <span className="grid h-9 w-9 place-items-center rounded-btn bg-brand text-white">
            <BookMarked size={18} />
          </span>
          <span className="text-[18px] tracking-tight">Skripsa</span>
        </Link>

        <Card>
          <div className="grid grid-cols-2 gap-1 rounded-btn bg-black/5 p-1 text-[13px] font-medium">
            {(["masuk", "daftar"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                className={`rounded-btn py-2 transition-colors duration-200 ${mode === m ? "bg-white shadow-sm" : "text-black/55"}`}
              >
                {m === "masuk" ? "Masuk" : "Daftar"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-5 space-y-4">
            {register && (
              <>
                <div>
                  <Label htmlFor="fullName">Nama lengkap</Label>
                  <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="major">Program studi</Label>
                    <Input id="major" value={majorName} onChange={(e) => setMajorName(e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="campus">Kampus</Label>
                    <Input id="campus" value={campusName} onChange={(e) => setCampusName(e.target.value)} />
                  </div>
                </div>
              </>
            )}
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </div>
            <div>
              <Label htmlFor="password">Kata sandi</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={register ? "new-password" : "current-password"}
              />
              {register && <FieldHint>Minimal 8 karakter.</FieldHint>}
              {!register && (
                <Link href="/lupa" className="mt-1.5 inline-block text-[12.5px] font-medium text-brand underline underline-offset-2">
                  Lupa password?
                </Link>
              )}
            </div>

            {error && <p className="text-[13px] text-vermillion">{error}</p>}

            <Button type="submit" size="lg" className="w-full" disabled={!valid || busy}>
              {busy && <Loader2 size={16} className="animate-spin" />}
              {register ? "Buat akun" : "Masuk"}
            </Button>
          </form>
        </Card>
      </div>
    </main>
  );
}
