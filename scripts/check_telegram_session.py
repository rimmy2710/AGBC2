#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is importable even when PYTHONPATH is not set
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from news_agent.pipeline.telethon_client import build_telegram_client


def main() -> int:
    api_id = (os.getenv("TELEGRAM_API_ID") or "").strip()
    api_hash = (os.getenv("TELEGRAM_API_HASH") or "").strip()
    if not api_id or not api_hash:
        print("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH", flush=True)
        return 2

    api_id_int = int(api_id)

    # Prefer StringSession
    string_session = (os.getenv("TELEGRAM_STRING_SESSION") or "").strip()
    if string_session:
        print("using_string_session=True (TELEGRAM_STRING_SESSION present)", flush=True)
        session_path = ""  # build_telegram_client will read TELEGRAM_STRING_SESSION
    else:
        agbc2_home = Path(os.getenv("AGBC2_HOME", str(Path.home() / ".agbc2")))
        default_path = agbc2_home / "secrets" / "telegram.session"
        session_path = (os.getenv("TELEGRAM_SESSION_PATH") or str(default_path)).strip()
        print(f"using_string_session=False (no TELEGRAM_STRING_SESSION). session_path={session_path}", flush=True)
        if not Path(session_path).exists():
            print(f"telegram_session_present=0 missing_file={session_path}", flush=True)
            return 3
        print("telegram_session_present=1", flush=True)

    client = build_telegram_client(api_id_int, api_hash, session_path)

    import asyncio

    async def _run():
        await client.connect()
        try:
            ok = await client.is_user_authorized()
            print("is_user_authorized=", ok, flush=True)
            if ok:
                me = await client.get_me()
                print("me=", getattr(me, "username", None), "id=", getattr(me, "id", None), flush=True)
            return 0 if ok else 4
        finally:
            await client.disconnect()

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
