from __future__ import annotations

import os
from telethon import TelegramClient

def build_telegram_client(api_id: int, api_hash: str, session_path: str) -> TelegramClient:
    """
    Prefer TELEGRAM_STRING_SESSION when present (no OTP re-login each time).
    Fallback to file session_path (sqlite) otherwise.
    """
    s = (os.getenv("TELEGRAM_STRING_SESSION") or "").strip()
    if s:
        from telethon.sessions import StringSession
        return TelegramClient(StringSession(s), api_id, api_hash)

    # fallback: sqlite session file path
    return TelegramClient(session_path, api_id, api_hash)
