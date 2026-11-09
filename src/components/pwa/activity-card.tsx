"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { api } from "@/lib/api";
import type { Activity } from "@/lib/types";
import { Flame } from "lucide-react";
import { useEffect, useState } from "react";

/** Target kata harian, streak, dan grafik 14 hari. Hanya penambahan kata yang dihitung. */
export function ActivityCard() {
  const [a, setA] = useState<Activity | null>(null);
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getActivity()
      .then((r) => (setA(r), setGoal(String(r.goal))))
      .catch((e) => setError(e instanceof Error ? e.message : "Gagal memuat"));
  }, []);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.setDailyGoal(Number(goal));
      setA(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menyimpan");
    } finally {
      setBusy(false);
    }
  };

  const max = Math.max(a?.goal ?? 1, ...(a?.series.map((s) => s.words) ?? [0]));
  const pct = a ? Math.min(100, Math.round((a.today / a.goal) * 100)) : 0;

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="yellow">
          <Flame size={12} /> Kebiasaan menulis
        </Pill>
        {a && a.streak > 0 && <Pill tone="green">{a.streak} hari beruntun</Pill>}
      </div>
      <h2 className="t-heading-sm mt-3">Target harian</h2>
      {a && (
        <>
          <p className="mt-1 text-[13px] text-graphite">
            Hari ini {a.today} dari {a.goal} kata. Total {a.total.toLocaleString("id-ID")} kata sejak mulai.
          </p>
          <div className="mt-2 h-2 overflow-hidden rounded-pill bg-black/8">
            <div className="h-full rounded-pill bg-brand transition-all" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-4 flex h-16 items-end gap-1" aria-label="Kata per hari, 14 hari terakhir" role="img">
            {a.series.map((s) => (
              <div key={s.day} title={`${s.day}: ${s.words} kata`} className={`flex-1 rounded-t-[3px] ${s.words >= a.goal ? "bg-brand" : s.words > 0 ? "bg-sky-wash" : "bg-black/10"}`} style={{ height: `${Math.max(4, (s.words / max) * 100)}%` }} />
            ))}
          </div>
        </>
      )}
      <div className="mt-4 flex items-end gap-2">
        <div className="w-40">
          <Label htmlFor="goal">Target kata/hari</Label>
          <Input id="goal" type="number" inputMode="numeric" min={50} max={5000} value={goal} onChange={(e) => setGoal(e.target.value)} />
        </div>
        <Button variant="ghost" onClick={save} loading={busy} disabled={busy || !goal}>
          Simpan
        </Button>
      </div>
      {error && <p className="mt-2 text-[13px] text-vermillion">{error}</p>}
    </Card>
  );
}
