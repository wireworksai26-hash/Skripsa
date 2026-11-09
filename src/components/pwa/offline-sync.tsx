"use client";

import { api } from "@/lib/api";
import { flushQueue, pendingCount } from "@/lib/offline-queue";
import { useAuth } from "@/lib/store";
import { useEffect, useState } from "react";

/** Mengirim suntingan yang tertahan saat offline dan menampilkan status koneksi singkat. */
export function OfflineSync() {
  const session = useAuth((s) => s.session);
  const [offline, setOffline] = useState(false);
  const [waiting, setWaiting] = useState(0);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    const flush = async () => {
      if (pendingCount() === 0) return;
      const n = await flushQueue(async (id, code, content) => {
        await api.saveSection(id, code, content);
      });
      setWaiting(pendingCount());
      if (n > 0) {
        setNote(`${n} suntingan yang tertahan sudah terkirim.`);
        setTimeout(() => setNote(null), 4000);
      }
    };
    const on = () => (setOffline(false), void flush());
    const off = () => (setOffline(true), setWaiting(pendingCount()));
    setOffline(!navigator.onLine);
    setWaiting(pendingCount());
    void flush();
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    const t = setInterval(() => setWaiting(pendingCount()), 3000);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
      clearInterval(t);
    };
  }, [session]);

  if (!offline && waiting === 0 && !note) return null;
  return (
    <div role="status" className="safe-bottom pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center px-3 pb-3">
      <p className="pointer-events-auto rounded-pill bg-midnight px-4 py-2 text-[13px] text-white shadow-lg">
        {note ?? (offline ? `Offline. ${waiting > 0 ? `${waiting} suntingan disimpan di perangkat dan dikirim otomatis nanti.` : "Perubahan tertahan sampai tersambung."}` : `${waiting} suntingan menunggu dikirim…`)}
      </p>
    </div>
  );
}
