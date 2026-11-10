"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { askConfirm } from "@/components/ui/confirm";
import { Input, Label } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import { useAuth, useProfile } from "@/lib/store";
import { Download, KeyRound, MailCheck, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

type Msg = { ok: boolean; text: string } | null;

/** Keamanan akun: ganti password, verifikasi email, ekspor semua data, dan hapus akun. */
export function AccountCard() {
  const router = useRouter();
  const signOut = useAuth((s) => s.signOut);
  const profile = useProfile((s) => s.profile);
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [delPw, setDelPw] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg>(null);

  const run = async (key: string, fn: () => Promise<string | void>) => {
    setBusy(key);
    setMsg(null);
    try {
      const text = await fn();
      if (text) setMsg({ ok: true, text });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Gagal" });
    } finally {
      setBusy(null);
    }
  };

  const changePw = () =>
    run("pw", async () => {
      await api.changePassword(cur, next);
      setCur("");
      setNext("");
      return "Password diganti.";
    });

  const exportData = () =>
    run("export", async () => {
      const blob = await api.exportMyData();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "skripsiai-data-saya.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return "Data Anda diunduh sebagai JSON.";
    });

  const verify = () =>
    run("verify", async () => {
      await api.sendVerification();
      return "Tautan verifikasi dikirim ke email Anda.";
    });

  const remove = async () => {
    const ok = await askConfirm("Akun, semua proyek, draf, data penelitian, dan komentar pembimbing akan dihapus permanen dan tidak bisa dikembalikan. Unduh data Anda dulu bila perlu.", {
      title: "Hapus akun?",
      confirmLabel: "Hapus akun",
      danger: true,
    });
    if (!ok) return;
    await run("del", async () => {
      await api.deleteAccount(delPw);
      signOut();
      router.replace("/masuk");
    });
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">
          <KeyRound size={12} /> Akun
        </Pill>
        {profile?.emailVerified ? <Pill tone="green">Email terverifikasi</Pill> : <Pill tone="yellow">Email belum diverifikasi</Pill>}
      </div>
      <h2 className="t-heading-sm mt-3">Keamanan dan data Anda</h2>

      {!profile?.emailVerified && (
        <div className="mt-3">
          <Button variant="ghost" size="sm" onClick={verify} loading={busy === "verify"} disabled={busy !== null}>
            {busy !== "verify" && <MailCheck size={14} />} Kirim tautan verifikasi
          </Button>
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="curpw">Password saat ini</Label>
          <Input id="curpw" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="newpw">Password baru (min. 8 karakter)</Label>
          <Input id="newpw" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </div>
      </div>
      <Button className="mt-3" variant="ghost" onClick={changePw} loading={busy === "pw"} disabled={busy !== null || !cur || next.length < 8}>
        Ganti password
      </Button>

      <div className="mt-5 border-t border-hairline pt-4">
        <p className="text-[13px] text-graphite">Unduh seluruh data Anda (profil, proyek, draf, rujukan, data penelitian) dalam satu berkas JSON.</p>
        <Button className="mt-2" variant="ghost" onClick={exportData} loading={busy === "export"} disabled={busy !== null}>
          {busy !== "export" && <Download size={15} />} Unduh data saya
        </Button>
      </div>

      <div className="mt-5 rounded-card border border-vermillion/30 bg-vermillion/5 p-3">
        <p className="text-[13.5px] font-semibold text-vermillion">Hapus akun</p>
        <p className="mt-0.5 text-[12.5px] text-black/60">Permanen. Masukkan password untuk melanjutkan.</p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <Input aria-label="Password untuk hapus akun" type="password" autoComplete="current-password" value={delPw} onChange={(e) => setDelPw(e.target.value)} />
          <Button variant="danger" onClick={remove} loading={busy === "del"} disabled={busy !== null || !delPw}>
            {busy !== "del" && <Trash2 size={15} />} Hapus akun
          </Button>
        </div>
      </div>
      {msg && <p className={msg.ok ? "mt-3 text-[13px] text-[#0a5f1e]" : "mt-3 text-[13px] text-vermillion"}>{msg.text}</p>}
    </Card>
  );
}
