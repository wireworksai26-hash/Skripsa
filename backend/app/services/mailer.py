"""Pengirim email sederhana (SMTP). Tanpa konfigurasi, fitur yang butuh email dinonaktifkan dengan pesan jelas."""

import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import settings


def is_configured() -> bool:
    return bool(settings.smtp_host and (settings.smtp_from or settings.smtp_user))


def _send(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


async def send_mail(to: str, subject: str, body: str) -> bool:
    """True bila terkirim. Kegagalan jaringan/SMTP tidak melempar (alur utama tidak boleh jatuh)."""
    if not is_configured():
        return False
    try:
        await asyncio.to_thread(_send, to, subject, body)
        return True
    except (OSError, smtplib.SMTPException):
        return False
