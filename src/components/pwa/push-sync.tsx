"use client";

import { pushConfigured, pushLogin, pushLogout } from "@/lib/push";
import { useAuth } from "@/lib/store";
import { useEffect, useRef } from "react";

/** Mengikat akun ke OneSignal (external_id = user_id) saat masuk dan melepasnya saat keluar. Tidak meminta izin apa pun. */
export function PushSync() {
  const session = useAuth((s) => s.session);
  const hydrate = useAuth((s) => s.hydrate);
  const last = useRef<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!pushConfigured) return;
    const id = session?.userId ?? null;
    if (id === last.current) return;
    const prev = last.current;
    last.current = id;
    if (id) void pushLogin(id).catch(() => undefined);
    else if (prev) void pushLogout().catch(() => undefined);
  }, [session]);

  return null;
}
