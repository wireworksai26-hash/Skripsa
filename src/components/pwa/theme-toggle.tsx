"use client";

import { Moon, Smartphone, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export type ThemePref = "auto" | "light" | "dark";
const KEY = "skripsi-ai-theme";

/** Terapkan pilihan ke <html>. "auto" mengikuti pengaturan sistem perangkat. */
export function applyTheme(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#141413" : "#f6f5f4");
}

export function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>("auto");

  useEffect(() => {
    let saved: ThemePref = "auto";
    try {
      const v = localStorage.getItem(KEY);
      if (v === "light" || v === "dark") saved = v;
    } catch {
      /* penyimpanan diblokir */
    }
    setPref(saved);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => saved === "auto" && applyTheme("auto");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const choose = (p: ThemePref) => {
    setPref(p);
    try {
      if (p === "auto") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, p);
    } catch {
      /* abaikan */
    }
    applyTheme(p);
  };

  const opts: Array<[ThemePref, string, typeof Sun]> = [
    ["auto", "Otomatis", Smartphone],
    ["light", "Terang", Sun],
    ["dark", "Gelap", Moon],
  ];
  return (
    <div role="radiogroup" aria-label="Tampilan" className="inline-flex rounded-btn bg-black/5 p-0.5">
      {opts.map(([v, label, Icon]) => (
        <button
          key={v}
          role="radio"
          aria-checked={pref === v}
          type="button"
          onClick={() => choose(v)}
          className={`inline-flex min-h-10 items-center gap-1.5 rounded-btn px-3 text-[13px] font-medium transition-colors ${pref === v ? "bg-white shadow-sm" : "text-black/55"}`}
        >
          <Icon size={14} /> {label}
        </button>
      ))}
    </div>
  );
}

/** Tombol ikon: terang <-> gelap. Pilihan eksplisit disimpan; "Otomatis" tetap tersedia di halaman Profil. */
export function ThemeButton({ className = "" }: { className?: string }) {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const read = () => setDark(document.documentElement.dataset.theme === "dark");
    read();
    const obs = new MutationObserver(read);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  const toggle = () => {
    const next: ThemePref = dark ? "light" : "dark";
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* abaikan */
    }
    applyTheme(next);
  };
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Ganti ke mode terang" : "Ganti ke mode gelap"}
      title={dark ? "Mode terang" : "Mode gelap"}
      className={`inline-flex h-10 w-10 items-center justify-center rounded-btn text-black/70 transition-colors hover:bg-black/5 ${className}`}
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
