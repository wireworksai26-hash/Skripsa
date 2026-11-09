import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function Pill({
  tone = "basic",
  className,
  children,
}: {
  tone?: "basic" | "blue" | "yellow" | "coral" | "midnight" | "green" | "sky";
  className?: string;
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    basic: "bg-black/5 text-black/80",
    blue: "bg-sky-tint text-brand",
    yellow: "bg-marigold text-[#1a1a1a]",
    coral: "bg-coral text-white",
    midnight: "bg-midnight text-white",
    green: "bg-[#d7f2d9] text-[#0a5f1e]",
    sky: "bg-sky-wash/30 text-[#04639b] border border-sky-wash/40 dark:bg-[#93c5fd]/10 dark:text-[#93c5fd] dark:border-[#93c5fd]/35",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-pill px-3 py-1 text-[12px] font-medium",
        tones[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
