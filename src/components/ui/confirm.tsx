"use client";

import { Button } from "@/components/ui/button";
import { useEffect, useSyncExternalStore } from "react";

interface Pending {
  message: string;
  title: string;
  confirmLabel: string;
  danger: boolean;
  resolve: (ok: boolean) => void;
}

let pending: Pending | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

/** Pengganti window.confirm: dialog sendiri yang konsisten di PWA dan ponsel. Mengembalikan true bila pengguna setuju. */
export function askConfirm(message: string, opts: { title?: string; confirmLabel?: string; danger?: boolean } = {}): Promise<boolean> {
  return new Promise((resolve) => {
    pending?.resolve(false);
    pending = { message, title: opts.title ?? "Konfirmasi", confirmLabel: opts.confirmLabel ?? "Lanjutkan", danger: opts.danger ?? false, resolve };
    emit();
  });
}

function close(ok: boolean) {
  const p = pending;
  pending = null;
  emit();
  p?.resolve(ok);
}

/** Pasang sekali di layout root. */
export function ConfirmHost() {
  const current = useSyncExternalStore(
    (cb) => (listeners.add(cb), () => void listeners.delete(cb)),
    () => pending,
    () => null
  );

  useEffect(() => {
    if (!current) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current]);

  if (!current) return null;
  return (
    <div className="fixed inset-0 z-[60] grid items-end bg-black/40 sm:place-items-center sm:p-4" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" onClick={(e) => e.target === e.currentTarget && close(false)}>
      <div className="safe-bottom w-full max-w-sm rounded-t-2xl bg-white p-5 sm:rounded-card sm:p-6">
        <h2 id="confirm-title" className="t-heading-sm">
          {current.title}
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-black/70">{current.message}</p>
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="text" onClick={() => close(false)} autoFocus>
            Batal
          </Button>
          <Button variant={current.danger ? "primary" : "primary"} className={current.danger ? "!bg-vermillion hover:!bg-[#c4260f]" : ""} onClick={() => close(true)}>
            {current.confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
