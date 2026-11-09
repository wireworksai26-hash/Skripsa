"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAuth, useProject } from "@/lib/store";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

/** Memastikan pengguna sudah login dan proyek aktif sudah dimuat dari server sebelum wizard tampil. */
export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const session = useAuth((s) => s.session);
  const ready = useAuth((s) => s.ready);
  const hydrate = useAuth((s) => s.hydrate);
  const loadActive = useProject((s) => s.loadActive);

  const [booted, setBooted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (ready && !session) router.replace("/masuk");
  }, [ready, session, router]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    setError(null);
    loadActive()
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Gagal memuat proyek");
      })
      .finally(() => {
        if (!cancelled) setBooted(true);
      });
    return () => {
      cancelled = true;
    };
  }, [session, loadActive, attempt]);

  if (!ready || !session || !booted) {
    return (
      <div className="grid min-h-[40vh] place-items-center text-[13px] text-black/50">
        <span className="inline-flex items-center gap-2">
          <Loader2 size={16} className="animate-spin" /> Memuat…
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="mx-auto mt-10 max-w-md text-center">
        <h2 className="t-heading-sm">Proyek tidak dapat dimuat</h2>
        <p className="mt-2 text-[13px] text-vermillion">{error}</p>
        <div className="mt-4 flex justify-center gap-2">
          <Button
            variant="primary"
            onClick={() => {
              setBooted(false);
              setAttempt((n) => n + 1);
            }}
          >
            Coba lagi
          </Button>
        </div>
      </Card>
    );
  }

  return <>{children}</>;
}
