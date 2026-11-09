"use client";

import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function InstallButton({ className, quiet = false }: { className?: string; quiet?: boolean }) {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
    };
  }, []);

  if (!deferred) return null;

  return (
    <Button
      variant={quiet ? "text" : "ghost"}
      size={quiet ? "sm" : "lg"}
      className={className}
      aria-label="Pasang sebagai aplikasi"
      onClick={() => {
        deferred.prompt();
        deferred.userChoice.finally(() => setDeferred(null));
      }}
    >
      <Download size={15} aria-hidden /> <span className={quiet ? "hidden md:inline" : ""}>{quiet ? "Pasang" : "Instal sebagai aplikasi"}</span>
    </Button>
  );
}
