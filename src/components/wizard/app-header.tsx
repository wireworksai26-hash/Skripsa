"use client";

import { askConfirm } from "@/components/ui/confirm";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/ui/pill";
import { useAuth, useProject } from "@/lib/store";
import { METHOD_LABEL } from "@/lib/types";
import { countWords } from "@/lib/utils";
import { BookMarked, FilePlus2, History, LogOut, MoreVertical, Server, Trash2, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ThemeButton } from "@/components/pwa/theme-toggle";
import { SettingsDialog } from "@/components/wizard/settings-dialog";

const iconLink =
  "inline-flex min-h-10 items-center gap-1.5 rounded-btn px-2.5 py-1.5 text-[13px] font-medium text-black/70 hover:bg-black/5 sm:min-h-0 sm:px-3";

export function AppHeader() {
  const router = useRouter();
  const project = useProject((s) => s.project);
  const closeProject = useProject((s) => s.closeProject);
  const deleteProject = useProject((s) => s.deleteProject);
  const session = useAuth((s) => s.session);
  const signOut = useAuth((s) => s.signOut);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const total = project ? project.sections.reduce((a, s) => a + countWords(s.content), 0) : 0;
  const summary = project ? `${METHOD_LABEL[project.form.method]} · ${total} kata draf · ${project.selectedRefIds.length} rujukan` : "Belum ada proyek aktif";

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuOpen]);

  const onDelete = async () => {
    setMenuOpen(false);
    if (!(await askConfirm("Hapus proyek ini dari server? Tindakan ini tidak bisa dibatalkan.", { danger: true }))) return;
    try {
      await deleteProject();
      router.replace("/proyek/1-inisiasi");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menghapus proyek");
    }
  };
  const onNew = () => {
    setMenuOpen(false);
    closeProject();
    router.replace("/proyek/1-inisiasi");
  };
  const onSignOut = () => {
    setMenuOpen(false);
    signOut();
    router.replace("/masuk");
  };

  const menuItem = "flex min-h-11 w-full items-center gap-2.5 rounded-btn px-3 text-left text-[14px] hover:bg-black/5";

  return (
    <>
      <header className="safe-top sticky top-0 z-40 border-b border-hairline bg-canvas/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-3 sm:h-16 sm:gap-3 sm:px-4">
          <Link href="/" className="flex shrink-0 items-center gap-2 font-bold">
            <span className="grid h-8 w-8 place-items-center rounded-btn bg-brand text-white">
              <BookMarked size={17} />
            </span>
            <span className="text-[17px] tracking-tight">Skripsa</span>
          </Link>

          <div className="ml-2 hidden min-w-0 lg:block">
            {error ? <p className="truncate text-[13px] text-vermillion">{error}</p> : <p className={project ? "truncate text-[13px] text-black/60" : "text-[13px] text-black/40"}>{summary}</p>}
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-1">
            {project && (
              <Pill tone={project.pickedTitleId ? "blue" : "basic"} className="mr-1 hidden sm:inline-flex">
                {project.status === "IN_PROGRESS" ? "Berlangsung" : "Draf Final"}
              </Pill>
            )}
            <ThemeButton />
            <Link href="/riwayat" className={iconLink} aria-label="Riwayat proyek">
              <History size={16} />
              <span className="hidden sm:inline">Riwayat</span>
            </Link>
            <Link href="/profil" className={iconLink} aria-label="Profil dan data sampul">
              <UserRound size={16} />
              <span className="hidden sm:inline">Profil</span>
            </Link>

            {/* Layar lebar: semua aksi sebaris */}
            <div className="hidden items-center gap-1 sm:flex">
              <Button variant="text" size="sm" onClick={() => setSettingsOpen(true)} aria-label="Status server">
                <Server size={16} />
                <span className="hidden md:inline">Server</span>
              </Button>
              {project && (
                <>
                  <Button variant="text" size="sm" onClick={onNew} aria-label="Proyek baru">
                    <FilePlus2 size={15} />
                    <span className="hidden md:inline">Proyek baru</span>
                  </Button>
                  <Button variant="danger" size="sm" onClick={onDelete} aria-label="Hapus proyek">
                    <Trash2 size={15} />
                  </Button>
                </>
              )}
              {session && (
                <Button variant="text" size="sm" onClick={onSignOut} aria-label={`Keluar (${session.email})`}>
                  <LogOut size={15} />
                  <span className="hidden md:inline">Keluar</span>
                </Button>
              )}
            </div>

            {/* Ponsel: aksi lain masuk menu */}
            <div ref={menuRef} className="relative sm:hidden">
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-btn text-black/70 hover:bg-black/5"
                aria-label="Menu lainnya"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((v) => !v)}
              >
                <MoreVertical size={18} />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-11 z-50 w-56 rounded-card border border-hairline bg-white p-1.5 shadow-lg" role="menu">
                  <button className={menuItem} role="menuitem" onClick={() => { setMenuOpen(false); setSettingsOpen(true); }}>
                    <Server size={16} /> Status server
                  </button>
                  {project && (
                    <>
                      <button className={menuItem} role="menuitem" onClick={onNew}>
                        <FilePlus2 size={16} /> Proyek baru
                      </button>
                      <button className={`${menuItem} text-vermillion`} role="menuitem" onClick={onDelete}>
                        <Trash2 size={16} /> Hapus proyek ini
                      </button>
                    </>
                  )}
                  {session && (
                    <button className={`${menuItem} border-t border-hairline`} role="menuitem" onClick={onSignOut}>
                      <LogOut size={16} /> Keluar
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        <p className="truncate border-t border-hairline/60 px-3 py-1 text-[12px] text-black/50 lg:hidden">{error ?? summary}</p>
      </header>
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
