import { cn } from "@/lib/utils";
import { forwardRef } from "react";
import type {
  InputHTMLAttributes,
  LabelHTMLAttributes,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn("mb-1.5 block text-sm font-medium text-black/95", className)}
      {...props}
    />
  );
}

const fieldCls =
  "w-full rounded-btn border border-hairline bg-white px-3.5 py-2.5 text-base text-ink lg:text-[15px] outline-none transition-colors duration-200 placeholder:text-black/35 focus:border-brand focus:ring-2 focus:ring-brand/15";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn(fieldCls, className)} {...props} />;
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, rows = 4, ...props }, ref) {
  return (
    <textarea ref={ref} rows={rows} className={cn(fieldCls, "resize-y", className)} {...props} />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...props }, ref) {
  return (
    <select ref={ref} className={cn(fieldCls, "select-chevron appearance-none pr-9", className)} {...props}>
      {children}
    </select>
  );
});

export function FieldHint({ children }: { children: React.ReactNode }) {
  return <p className="mt-1.5 text-[13px] text-black/45">{children}</p>;
}
