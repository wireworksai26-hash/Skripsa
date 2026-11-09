"""Ekstraksi komponen penelitian (variabel X/Y, subjek, metode, jurusan) dari sebuah judul skripsi."""

from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex

METHODS = {"KUANTITATIF", "KUALITATIF", "MIXED_METHODS", "RND"}
DOMAINS = {"INFORMATIKA", "ENGLISH_EDUCATION", "UMUM"}

SYSTEM = (
    "Kamu mengekstrak komponen penelitian dari JUDUL skripsi/tesis (bahasa Indonesia atau Inggris).\n"
    "Aturan:\n"
    "1. Isi HANYA yang tersurat atau jelas tersirat di judul. Dilarang menambah informasi dari luar judul.\n"
    "2. variable_x = fokus/variabel utama pertama; variable_y = fokus/variabel kedua. Pada penelitian pengaruh/hubungan: "
    "X = variabel bebas, Y = variabel terikat. Pada studi kasus/kualitatif: X dan Y = dua fokus yang dikaji. "
    "Bila judul hanya punya satu fokus, isi variable_y dengan string kosong.\n"
    "3. Tulis variabel sebagai frasa nominal singkat (2-7 kata) dalam BAHASA JUDULNYA, tanpa kata 'pengaruh/effect of'.\n"
    "4. subject = siapa/di mana penelitian dilakukan, sesingkat mungkin; kosong bila tidak disebut.\n"
    "5. method: KUANTITATIF, KUALITATIF, MIXED_METHODS, atau RND hanya bila ada petunjuk di judul "
    "(mis. 'case study/studi kasus/persepsi' = KUALITATIF; 'pengaruh/hubungan/efektivitas' = KUANTITATIF; "
    "'pengembangan/development' = RND). Selain itu null.\n"
    "6. domain: INFORMATIKA (sistem informasi, perangkat lunak, AI/data), ENGLISH_EDUCATION (pengajaran bahasa Inggris), "
    "atau UMUM.\n"
    "7. note: satu kalimat bahasa Indonesia tentang apa yang kurang jelas dan perlu diperiksa pengguna (boleh kosong).\n"
    'Tanggapi HANYA JSON: {"variable_x":"","variable_y":"","subject":"","method":null,"domain":"UMUM","note":""}'
)


def _clean(value, limit: int) -> str:
    return " ".join(str(value or "").split()).strip(" .;:,\"'")[:limit]


def normalize(data: dict) -> dict:
    method = str(data.get("method") or "").strip().upper().replace(" ", "_")
    domain = str(data.get("domain") or "").strip().upper().replace(" ", "_")
    return {
        "variable_x": _clean(data.get("variable_x"), 160),
        "variable_y": _clean(data.get("variable_y"), 160),
        "subject": _clean(data.get("subject"), 200),
        "method": method if method in METHODS else None,
        "domain": domain if domain in DOMAINS else "UMUM",
        "note": _clean(data.get("note"), 300),
    }


async def extract_from_title(title: str) -> tuple[dict, str]:
    """Kembalikan (komponen, penyedia). Melempar LLMUnavailable bila LLM gagal atau tak menemukan variabel apa pun."""
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Judul: {title.strip()}"}]
    last = "tidak ada jawaban"
    for _ in range(2):
        raw, provider = await llm_chat_ex(messages, tier="fast", temperature=0.1, max_tokens=700)
        try:
            out = normalize(extract_json(raw))
        except ValueError as exc:
            last = f"JSON tidak valid ({exc})"
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Jawabanmu bukan JSON valid. Balas HANYA dengan satu objek JSON sesuai format."},
            ]
            continue
        if out["variable_x"]:
            return out, provider
        last = "tidak ada variabel yang terbaca dari judul"
        break
    raise LLMUnavailable(f"Variabel tidak dapat diekstrak: {last}")
