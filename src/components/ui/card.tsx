import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function Card({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("rounded-card border border-hairline bg-white p-4 sm:p-6", className)}>
      {children}
    </div>
  );
}

const tones: Record<string, string> = {
  marigold: "bg-marigold",
  coral: "bg-coral",
  "sky-wash": "bg-sky-wash",
  midnight: "bg-midnight text-white",
  saffron: "bg-saffron",
  mocha: "bg-mocha text-white",
  sky: "bg-sky-tint",
};

export function AccentCard({
  tone = "marigold",
  className,
  children,
}: {
  tone?: keyof typeof tones;
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn("rounded-card p-4 sm:p-6", tones[tone], className)}>{children}</div>;
}
