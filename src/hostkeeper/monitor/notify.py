"""Pengirim notifikasi webhook (Slack, Discord, JSON) untuk monitoring hostkeeper."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import IO, Any


def mask_url(url: str) -> str:
    """Menyamarkan URL webhook agar token atau path rahasia tidak bocor."""
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return "******"

        path = parsed.path
        if "/webhooks/" in path:
            prefix = path.split("/webhooks/")[0] + "/webhooks"
            return f"{parsed.scheme}://{parsed.netloc}{prefix}/******"
        if "/services/" in path:
            prefix = path.split("/services/")[0] + "/services"
            return f"{parsed.scheme}://{parsed.netloc}{prefix}/******"

        if parsed.query:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?******"

        path_parts = [p for p in path.split("/") if p]
        if len(path_parts) > 1:
            masked_path = "/" + "/".join(path_parts[:-1]) + "/******"
        elif len(path_parts) == 1:
            masked_path = "/******"
        else:
            masked_path = ""

        return f"{parsed.scheme}://{parsed.netloc}{masked_path}"
    except Exception:
        return "******"


def format_payload(
    fmt: str,
    hostname: str,
    messages: list[str],
    level: str,
) -> dict[str, Any]:
    """Memformat payload pesan sesuai format target (slack, discord, json)."""
    fmt_lower = fmt.lower()
    tag = level.upper()
    body = "\n".join(f"- {m}" for m in messages)
    text = f"[{tag}] hostkeeper alert di {hostname}:\n{body}"

    if fmt_lower == "slack":
        return {"text": text}
    if fmt_lower == "discord":
        return {"content": text}
    return {
        "hostname": hostname,
        "level": level,
        "alerts": messages,
        "timestamp": time.time(),
    }


def send_webhook(
    url: str,
    payload: dict[str, Any],
    timeout: float = 5.0,
    out_err: IO[str] | None = None,
) -> bool:
    """Mengirim payload JSON ke webhook URL.

    Kegagalan dicatat tetapi tidak fatal (mengembalikan False).
    """
    err_stream = out_err if out_err is not None else sys.stderr
    masked = mask_url(url)

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "hostkeeper-watch",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            return bool(200 <= status < 300)
    except Exception as exc:
        err_stream.write(f"Peringatan: Gagal mengirim webhook ke {masked}: {exc}\n")
        return False


def check_watch_config_permissions(
    config_path: Path,
    out_err: IO[str] | None = None,
) -> bool:
    """Memeriksa apakah file watch.yml memiliki mode izin 0600."""
    err_stream = out_err if out_err is not None else sys.stderr
    if not config_path.is_file():
        return False

    try:
        mode = config_path.stat().st_mode & 0o777
        if mode != 0o600:
            err_stream.write(
                f"Peringatan keamanan: izin file {config_path} "
                f"adalah {oct(mode)}, bukan 0600.\n"
            )
            return True
    except OSError:
        pass
    return False
