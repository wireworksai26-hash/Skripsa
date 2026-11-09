"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const STEPS = [
  { n: 1, href: "/proyek/1-inisiasi", label: "Inisiasi" },
  { n: 2, href: "/proyek/2-judul", label: "Judul" },
  { n: 3, href: "/proyek/3-rujukan", label: "Rujukan" },
  { n: 4, href: "/proyek/4-draf", label: "Draf" },
  { n: 5, href: "/proyek/5-visual", label: "Visual" },
  { n: 6, href: "/proyek/6-review", label: "Review & Ekspor" },
];

export function Stepper() {
  const pathname = usePathname();
  const active = Number(pathname.split("/")[2]?.split("-")[0] ?? 1);
  const activeRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [active]);

  return (
    <nav
      aria-label="Langkah wizard"
      className="scroll-thin flex snap-x gap-1.5 overflow-x-auto rounded-card border border-hairline bg-white p-1.5 sm:gap-2 sm:p-2 lg:justify-center"
    >
      {STEPS.map((s) => {
        const isActive = s.n === active;
        const done = s.n < active;
        return (
          <Link
            key={s.n}
            ref={isActive ? activeRef : undefined}
            href={s.href}
            aria-current={isActive ? "step" : undefined}
            className={cn(
              "inline-flex min-h-10 shrink-0 snap-center items-center gap-2 rounded-pill px-3 py-2 text-[13px] sm:px-4 font-medium transition-colors duration-200",
              isActive
                ? "bg-brand text-white"
                : done
                  ? "bg-sky-tint text-brand"
                  : "text-black/55 hover:bg-black/5"
            )}
          >
            <span
              className={cn(
                "grid h-5 w-5 place-items-center rounded-full text-[11px] font-semibold",
                isActive || done
                  ? "bg-white/25 text-white lg:bg-white/0 lg:text-white"
                  : "bg-black/8 text-black/60"
              )}
            >
              {done ? <Check size={11} strokeWidth={3} /> : s.n}
            </span>
            <span className={cn(!isActive && "hidden sm:inline")}>{s.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
