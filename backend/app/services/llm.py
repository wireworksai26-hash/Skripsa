"""Orkestrasi LLM multi-penyedia.

Tiga penyedia memakai protokol OpenAI-compatible (`/chat/completions`), jadi satu klien cukup.
Tiap tugas meminta *tier*; tier menentukan urutan penyedia, dan kegagalan satu penyedia
(kuota 429, timeout, jawaban kosong) otomatis jatuh ke penyedia berikutnya.

  tier "fast"  -> tugas ringan/interaktif (judul, analisis celah)  : Groq -> Gemini -> NIM
  tier "heavy" -> tugas berat (draf subbab panjang berbasis RAG)   : NIM  -> Gemini -> Groq
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import settings

log = logging.getLogger("skripsi.llm")

Tier = Literal["fast", "heavy"]


class LLMUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str
    timeout: float
    extra_body: dict

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


def nim_models() -> list[str]:
    """Model NIM berurutan: utama lalu cadangan (tanpa duplikat)."""
    seen: list[str] = []
    for m in [settings.nim_model, *settings.nim_fallback_models.split(",")]:
        m = m.strip()
        if m and m not in seen:
            seen.append(m)
    return seen


def providers() -> dict[str, Provider]:
    table = {
        "groq": Provider("groq", settings.groq_base_url, settings.groq_api_key, settings.groq_model, 30, {}),
        "gemini": Provider("gemini", settings.gemini_base_url, settings.gemini_api_key, settings.gemini_model, 120, {}),
        "nim": Provider(
            "nim",
            settings.nim_base_url,
            settings.nim_api_key,
            (nim_models() or [""])[0],
            120,
            # Model penalaran NIM menghabiskan max_tokens untuk berpikir lalu mengembalikan content=null.
            {"chat_template_kwargs": {"enable_thinking": False}},
        ),
    }
    # Model NIM cadangan: penyedia sendiri agar bisa dipakai bergantian (nama = "nim:<model>").
    for m in nim_models()[1:]:
        key = f"nim:{m.split('/')[-1]}"
        table[key] = Provider(key, settings.nim_base_url, settings.nim_api_key, m, 120, {"chat_template_kwargs": {"enable_thinking": False}})
    return table


def route(tier: Tier) -> list[Provider]:
    order = settings.llm_fast_order if tier == "fast" else settings.llm_heavy_order
    table = providers()
    names = [n.strip().lower() for n in order.split(",") if n.strip()]
    chain: list[Provider] = []
    for n in names:
        # "nim" berarti model utama NIM lalu semua cadangannya, berurutan.
        group = [k for k in table if k == "nim" or k.startswith("nim:")] if n == "nim" else [n]
        chain += [table[k] for k in group if k in table and table[k].configured]
    return chain


def is_configured() -> bool:
    return any(p.configured for p in providers().values())


def status() -> dict:
    return {
        "providers": {n: p.configured for n, p in providers().items()},
        "models": {n: p.model for n, p in providers().items() if p.configured},
        "routing": {
            "fast": [p.name for p in route("fast")],
            "heavy": [p.name for p in route("heavy")],
        },
    }


# Tugas ringan harus cepat: penyedia yang lambat dilewati daripada ditunggu sampai batas waktu penuh.
FAST_TIER_TIMEOUT = 20.0


async def _call(p: Provider, messages: list[dict], temperature: float, max_tokens: int, timeout: float | None = None) -> str:
    body = {
        "model": p.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **p.extra_body,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {p.api_key}"}
    async with httpx.AsyncClient(timeout=timeout or p.timeout) as client:
        res = await client.post(f"{p.base_url.rstrip('/')}/chat/completions", json=body, headers=headers)
        res.raise_for_status()
        data = res.json()

    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
    if not content:
        raise LLMUnavailable("jawaban kosong")
    return content


async def llm_chat_ex(
    messages: list[dict],
    tier: Tier = "heavy",
    temperature: float = 0.4,
    max_tokens: int = 1600,
    only: str | None = None,
) -> tuple[str, str]:
    """Kembalikan (teks, nama_penyedia). Melempar LLMUnavailable bila semua penyedia gagal/tak dikonfigurasi.

    `only` mengunci satu penyedia; dipakai pemanggil yang ingin pindah penyedia karena mutu jawaban, bukan error.
    """
    chain = [p for p in route(tier) if only is None or p.name == only]
    if not chain:
        raise LLMUnavailable("Tidak ada penyedia LLM yang dikonfigurasi (isi kunci API di backend/.env)")

    failures: list[str] = []
    for p in chain:
        try:
            text = await _call(p, messages, temperature, max_tokens, min(p.timeout, FAST_TIER_TIMEOUT) if tier == "fast" else p.timeout)
            if failures:
                log.warning("tier=%s: jatuh ke %s setelah gagal: %s", tier, p.name, "; ".join(failures))
            return text, p.name
        except Exception as exc:  # 429, timeout, 4xx/5xx, JSON rusak: coba penyedia berikutnya
            failures.append(f"{p.name}: {type(exc).__name__} {str(exc)[:120]}")
    raise LLMUnavailable("Semua penyedia LLM gagal — " + "; ".join(failures))


async def llm_chat(
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int = 1600,
    tier: Tier = "heavy",
) -> str:
    return (await llm_chat_ex(messages, tier, temperature, max_tokens))[0]


def extract_json(raw: str) -> dict:
    start = raw.find("{")
    if start < 0:
        raise ValueError("Tidak ada blok JSON pada keluaran LLM")
    return json_loads_balanced(raw[start:])


def _balanced_object(text: str) -> str:
    """Ambil objek pertama yang kurung kurawalnya seimbang (abaikan kurawal di dalam string).

    Bila keluaran terpotong di tengah, kembalikan sisa teks apa adanya agar masih bisa diselamatkan.
    """
    depth = 0
    in_str = False
    escaped = False
    for i, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[: i + 1]
    return text


def _escape_controls(text: str) -> str:
    """Model kadang menulis baris baru mentah di dalam string JSON; itu melanggar spec."""
    out: list[str] = []
    in_str = False
    escaped = False
    for ch in text:
        if in_str:
            if escaped:
                escaped = False
                out.append(ch)
            elif ch == "\\":
                escaped = True
                out.append(ch)
            elif ch == '"':
                in_str = False
                out.append(ch)
            elif ch in ("\n", "\r", "\t"):
                out.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
            elif ord(ch) < 0x20:
                out.append(" ")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
    return "".join(out)


def json_loads_balanced(text: str) -> dict:
    import json

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    body = _balanced_object(text)
    candidates = (
        body,
        _escape_controls(body),
        re.sub(r",\s*([}\]])", r"\1", _escape_controls(body)),
    )
    last: Exception | None = None
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as exc:
            last = exc
    raise ValueError(f"JSON tidak dapat dibaca: {last}")
