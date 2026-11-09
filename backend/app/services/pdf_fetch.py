"""Pengambil PDF rujukan untuk panel pembaca (stabilo kuning).

Browser tidak bisa mengambil PDF repositori langsung (CORS), jadi server yang mengambilnya.
Karena server mengikuti URL dari pihak ketiga, tiap hop divalidasi agar tidak bisa dipakai
menembak jaringan internal (SSRF): hanya http/https, alamat publik, ukuran dibatasi, dan isinya harus PDF.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 30 * 1024 * 1024
MAX_REDIRECTS = 4
_UA = {"User-Agent": "SkripsiAI/1.0 (academic pdf viewer)", "Accept": "application/pdf,*/*;q=0.5"}


class PdfFetchError(Exception):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


async def _resolve_all(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({i[4][0] for i in infos})


def _is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%")[0])
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def assert_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PdfFetchError("Tautan PDF harus berupa http/https")
    host = parts.hostname
    try:
        addrs = [str(ipaddress.ip_address(host))]  # host sudah berupa IP
    except ValueError:
        try:
            addrs = await _resolve_all(host)
        except OSError:
            raise PdfFetchError("Alamat server PDF tidak ditemukan", 502)
    if not addrs or not all(_is_public(a) for a in addrs):
        raise PdfFetchError("Tautan PDF mengarah ke alamat non-publik dan ditolak", 400)


async def fetch_pdf(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=25, headers=_UA, follow_redirects=False) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await assert_public_url(current)
            try:
                async with client.stream("GET", current) as res:
                    if res.is_redirect:
                        location = res.headers.get("location")
                        if not location:
                            raise PdfFetchError("Pengalihan tanpa tujuan", 502)
                        current = urljoin(current, location)
                        continue
                    if res.status_code != 200:
                        raise PdfFetchError(f"Server PDF menjawab status {res.status_code}", 502)
                    declared = int(res.headers.get("content-length") or 0)
                    if declared > MAX_BYTES:
                        raise PdfFetchError("Berkas PDF terlalu besar (maks 30 MB)", 413)
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in res.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise PdfFetchError("Berkas PDF terlalu besar (maks 30 MB)", 413)
                        chunks.append(chunk)
            except httpx.HTTPError as exc:
                raise PdfFetchError(f"Gagal mengunduh PDF: {type(exc).__name__}", 502)
            data = b"".join(chunks)
            if not data.lstrip()[:5] == b"%PDF-":
                raise PdfFetchError("Tautan ini bukan berkas PDF langsung (kemungkinan halaman penerbit)", 415)
            return data
    raise PdfFetchError("Terlalu banyak pengalihan", 502)
