"use client";

import { Button } from "@/components/ui/button";
import { api, API_URL } from "@/lib/api";
import { Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

type Health = Awaited<ReturnType<typeof api.health>>;

/** Status backend: penyedia LLM yang aktif dan keterjangkauan API ilmiah. Kunci API hanya diisi di backend/.env. */
export function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    api
      .health()
      .then(setHealth)
      .catch((e) => {
        setHealth(null);
        setError(e instanceof Error ? e.message : "Gagal memeriksa server");
      })
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  const llm = health?.llm;

  return (
    <div className="fixed inset-0 z-50 grid items-end bg-black/40 sm:place-items-center sm:p-4" role="dialog" aria-modal="true" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="safe-bottom max-h-[88dvh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-5 sm:rounded-card sm:p-6">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="t-heading-sm">Status server</h2>
            <p className="mt-1 text-[13px] text-black/55">{API_URL}</p>
          </div>
          <Button variant="text" size="sm" onClick={onClose} aria-label="Tutup">
            <X size={16} />
          </Button>
        </div>

        {loading && (
          <p className="flex items-center gap-2 text-[13px] text-black/55">
            <Loader2 size={14} className="animate-spin" /> Memeriksa…
          </p>
        )}
        {error && <p className="text-[13px] text-vermillion">{error}</p>}

        {health && (
          <div className="space-y-5 text-[13px]">
            <section>
              <h3 className="font-semibold">Penyedia LLM</h3>
              {llm ? (
                <>
                  <ul className="mt-2 space-y-1">
                    {Object.entries(llm.providers).map(([name, on]) => (
                      <li key={name} className="flex justify-between border-b border-dashed border-hairline pb-1">
                        <span>
                          {name}
                          {on && llm.models[name] ? <span className="text-black/45"> · {llm.models[name]}</span> : null}
                        </span>
                        <span className={on ? "font-medium text-brand" : "text-black/40"}>{on ? "aktif" : "tanpa kunci"}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-black/60">
                    Tugas ringan (judul): {llm.routing.fast.join(" → ") || "—"}
                    <br />
                    Tugas berat (draf subbab): {llm.routing.heavy.join(" → ") || "—"}
                  </p>
                  {llm.routing.fast.length === 0 && (
                    <p className="mt-2 text-vermillion">Belum ada kunci LLM di backend/.env — judul dan draf memakai template lokal.</p>
                  )}
                </>
              ) : (
                <p className="mt-1 text-black/60">{health.llm_mode}</p>
              )}
            </section>

            <section>
              <h3 className="font-semibold">API ilmiah</h3>
              <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
                {Object.entries(health.scientific_apis).map(([name, status]) => (
                  <li key={name} className="flex justify-between">
                    <span>{name}</span>
                    <span className={status === 200 ? "text-brand" : "text-vermillion"}>{String(status)}</span>
                  </li>
                ))}
              </ul>
              <p className={`mt-2 ${health.unpaywall ? "text-black/60" : "text-vermillion"}`}>
                Unpaywall (tautan PDF terbuka lewat DOI):{" "}
                {health.unpaywall ? "aktif" : "nonaktif — isi SKRIPSI_POLITE_EMAIL dengan email asli di backend/.env"}
              </p>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
