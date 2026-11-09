"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { disablePush, enablePush, getPushState, needsIosInstall, type PushState } from "@/lib/push";
import type { NotifyPrefs } from "@/lib/types";
import { Bell, BellOff, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

const KINDS: Array<[keyof NotifyPrefs, string, string]> = [
  ["draft", "Draf selesai dibuat", "Saat pipeline selesai menulis semua subbab."],
  ["review", "Review selesai", "Saat panel Advisor, Examiner, dan Guardrail selesai menilai."],
  ["reminder", "Pengingat menulis", "Jika proyek berjalan tidak disentuh 3 hari (maksimal sekali per 3 hari)."],
];

/** Izin notifikasi perangkat ini + pilihan jenis notifikasi (pilihan disimpan bersama profil). */
export function NotifyCard({ prefs, onChange }: { prefs: NotifyPrefs; onChange: (p: NotifyPrefs) => void }) {
  const [state, setState] = useState<PushState | "loading">("loading");
  const [busy, setBusy] = useState(false);
  const [ios, setIos] = useState(false);

  useEffect(() => {
    setIos(needsIosInstall());
    getPushState()
      .then(setState)
      .catch(() => setState("unsupported"));
  }, []);

  const toggle = async () => {
    setBusy(true);
    try {
      setState(state === "on" ? await disablePush() : await enablePush());
    } catch {
      setState("unsupported");
    } finally {
      setBusy(false);
    }
  };

  const disabledNote: Partial<Record<PushState, string>> = {
    unconfigured: "Notifikasi belum dikonfigurasi di server ini (NEXT_PUBLIC_ONESIGNAL_APP_ID kosong).",
    unsupported: "Browser atau perangkat ini tidak mendukung notifikasi web.",
    denied: "Izin notifikasi diblokir di browser. Ubah lewat pengaturan situs, lalu muat ulang halaman.",
  };
  const note = state === "loading" ? null : disabledNote[state];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="blue">
          <Bell size={12} /> Notifikasi
        </Pill>
        {state === "on" && <Pill tone="green">Aktif di perangkat ini</Pill>}
      </div>
      <h2 className="t-heading-sm mt-3">Kabari saya</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-graphite">Notifikasi dikirim ke perangkat yang sudah Anda aktifkan, bahkan saat aplikasi ditutup.</p>

      {ios && (
        <p className="mt-3 rounded-btn bg-marigold/25 p-3 text-[12.5px] leading-relaxed text-black/75">
          Di iPhone/iPad, notifikasi hanya berfungsi setelah aplikasi dipasang: buka menu Bagikan di Safari, pilih <strong>Tambahkan ke Layar Utama</strong>, lalu buka dari ikon
          tersebut.
        </p>
      )}
      {note && <p className="mt-3 text-[12.5px] text-black/55">{note}</p>}

      <div className="mt-4 space-y-2">
        {KINDS.map(([k, label, hint]) => (
          <label key={k} className="flex min-h-11 cursor-pointer items-start gap-3 rounded-btn border border-hairline p-3">
            <input type="checkbox" className="mt-1" checked={prefs[k]} onChange={(e) => onChange({ ...prefs, [k]: e.target.checked })} />
            <span>
              <span className="block text-[14px] font-medium">{label}</span>
              <span className="block text-[12px] text-black/50">{hint}</span>
            </span>
          </label>
        ))}
      </div>
      <p className="mt-2 text-[11.5px] text-black/40">Pilihan jenis disimpan saat Anda menekan &ldquo;Simpan profil&rdquo;.</p>

      {!note && state !== "loading" && (
        <Button className="mt-4" variant={state === "on" ? "ghost" : "primary"} onClick={toggle} loading={busy}>
          {!busy && (state === "on" ? <BellOff size={15} /> : <Bell size={15} />)}
          {state === "on" ? "Matikan di perangkat ini" : "Aktifkan notifikasi"}
        </Button>
      )}
      {state === "loading" && (
        <p className="mt-4 flex items-center gap-2 text-[12.5px] text-black/45">
          <Loader2 size={13} className="animate-spin" /> Memeriksa dukungan…
        </p>
      )}
    </Card>
  );
}
