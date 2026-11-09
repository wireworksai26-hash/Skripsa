import type { ReactNode } from "react";
import { AppHeader } from "@/components/wizard/app-header";
import { AuthGate } from "@/components/wizard/auth-gate";

export default function RiwayatLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6">
        <AuthGate>{children}</AuthGate>
      </main>
    </div>
  );
}
