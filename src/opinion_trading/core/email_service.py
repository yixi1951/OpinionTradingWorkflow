"""Transactional email delivery with a safe development sink."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Dict


def send_transactional_email(to: str, subject: str, text: str) -> Dict[str, object]:
    host = (os.environ.get("SMTP_HOST") or "").strip()
    if not host:
        sink = Path(os.environ.get("EMAIL_SINK_PATH", "data/memory/email_outbox.jsonl"))
        sink.parent.mkdir(parents=True, exist_ok=True)
        import json
        from datetime import datetime, timezone

        with sink.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"to": to, "subject": subject, "text": text, "sent_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False) + "\n")
        return {"ok": True, "mode": "sink", "to": to}

    message = EmailMessage()
    message["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "noreply@localhost"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=15) as client:
        client.starttls()
        user, password = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
        if user and password:
            client.login(user, password)
        client.send_message(message)
    return {"ok": True, "mode": "smtp", "to": to}
