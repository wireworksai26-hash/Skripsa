"""Pembuat PDF minimal (font Helvetica, teks ASCII) untuk tes parser; tanpa dependensi tambahan."""


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[str]]) -> bytes:
    """Satu halaman = daftar baris teks. Halaman kosong ([]) menghasilkan halaman tanpa teks (seperti hasil pindai)."""
    objects: list[bytes] = []
    n = len(pages)
    font_id = 3 + 2 * n  # setelah katalog(1), pages(2), lalu pasangan halaman+konten
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, lines in enumerate(pages):
        page_id, content_id = 3 + 2 * i, 4 + 2 * i
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_id} 0 R "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode()
        )
        body = "BT /F1 10 Tf 40 800 Td 13 TL " + " ".join(f"({_esc(line)}) Tj T*" for line in lines) + " ET" if lines else ""
        stream = body.encode("latin-1")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


GUIDELINE_PAGES = [
    [
        "PEDOMAN PENULISAN SKRIPSI",
        "Universitas Contoh Nusantara",
        "Fakultas Teknik dan Informatika",
        "Pedoman ini berlaku bagi mahasiswa program sarjana (S1) pada seluruh program studi.",
        "Skripsi ditulis dengan bahasa Indonesia baku sesuai Pedoman Umum Ejaan Bahasa Indonesia.",
    ],
    [
        "BAB II FORMAT PENULISAN",
        "Naskah diketik pada kertas A4. Margin atas 4 cm, kiri 4 cm, bawah 3 cm, dan kanan 3 cm.",
        "Jenis huruf Times New Roman ukuran 12 pt dengan spasi 1,5 pada seluruh isi naskah.",
        "Awal paragraf menjorok ke dalam sebesar 1 cm dari tepi kiri.",
        "Sitasi dan daftar pustaka mengikuti gaya APA edisi ketujuh.",
    ],
    [
        "BAB III SISTEMATIKA SKRIPSI",
        "BAB I PENDAHULUAN: 1.1 Latar Belakang Masalah, 1.2 Rumusan Masalah, 1.3 Tujuan Penelitian, 1.4 Manfaat Penelitian.",
        "BAB II TINJAUAN PUSTAKA: 2.1 Landasan Teori, 2.2 Penelitian Terdahulu, 2.3 Kerangka Pemikiran.",
        "BAB III METODE PENELITIAN: 3.1 Desain Penelitian, 3.2 Populasi dan Sampel, 3.3 Teknik Analisis Data.",
        "BAB IV HASIL DAN PEMBAHASAN: 4.1 Hasil Penelitian, 4.2 Pembahasan.",
        "BAB V PENUTUP: 5.1 Simpulan, 5.2 Saran.",
    ],
]
