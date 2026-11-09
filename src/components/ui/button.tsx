import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, AnchorHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "text" | "outline" | "danger";
type Size = "sm" | "md" | "lg";

const variantClass: Record<Variant, string> = {
  // #0075de adalah satu-satunya tombol chromatic filled dalam sistem
  primary:
    "bg-brand text-white hover:bg-[#0065c4] active:bg-[#005ab0] transition-colors duration-200",
  ghost: "bg-sky-tint text-brand hover:bg-[#d6eafd] transition-colors duration-200",
  text: "text-black/95 hover:bg-black/5 transition-colors duration-200",
  outline:
    "border border-black/90 text-black/90 hover:bg-black/5 transition-colors duration-200 rounded-inline px-3 py-2 sm:px-2.5 sm:py-1",
  danger: "bg-transparent text-vermillion hover:bg-vermillion/10 transition-colors duration-200",
};

const sizeClass: Record<Size, string> = {
  sm: "h-10 px-3.5 text-[13px] sm:h-8",
  md: "h-11 px-5 text-sm sm:h-10",
  lg: "h-12 px-6 text-[15px] sm:h-11",
};

function base(variant: Variant, size: Size, className?: string) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-btn font-medium select-none whitespace-nowrap touch-manipulation active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none",
    variant === "outline" ? "" : sizeClass[size],
    variantClass[variant],
    className
  );
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  loading = false,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean }) {
  return (
    <button className={base(variant, size, className)} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {loading && <Loader2 size={15} className="animate-spin" />}
      {children}
    </button>
  );
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant; size?: Size }) {
  return (
    <a className={base(variant, size, className)} {...props}>
      {children}
    </a>
  );
}
