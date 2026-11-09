/** Antrean suntingan subbab saat offline: disimpan di perangkat, dikirim otomatis begitu tersambung lagi. */

const KEY = "skripsi-ai-pending-edits";

type Pending = Record<string, { thesisId: string; code: string; content: string; at: number }>;

function read(): Pending {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Pending;
  } catch {
    return {};
  }
}

function write(p: Pending) {
  try {
    if (Object.keys(p).length === 0) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* penyimpanan penuh/diblokir: suntingan tetap ada di layar */
  }
}

export function queueEdit(thesisId: string, code: string, content: string): void {
  const p = read();
  p[`${thesisId}:${code}`] = { thesisId, code, content, at: Date.now() };
  write(p);
}

export function pendingCount(): number {
  return Object.keys(read()).length;
}

/** Kirim semua yang tertunda. Mengembalikan jumlah yang berhasil terkirim; yang gagal tetap di antrean. */
export async function flushQueue(send: (thesisId: string, code: string, content: string) => Promise<void>): Promise<number> {
  const p = read();
  let sent = 0;
  for (const [k, v] of Object.entries(p)) {
    try {
      await send(v.thesisId, v.code, v.content);
      delete p[k];
      sent++;
    } catch {
      break; // masih offline atau ditolak; coba lagi nanti
    }
  }
  write(p);
  return sent;
}
