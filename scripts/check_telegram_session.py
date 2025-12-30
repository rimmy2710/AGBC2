import asyncio
import os
from news_agent.pipeline.telethon_client import build_telegram_client

async def main():
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_path = os.environ.get("TELEGRAM_SESSION_PATH", "/home/codespace/.agbc2/secrets/telegram.session")

    client = build_telegram_client(api_id, api_hash, session_path)
    async with client:
        ok = await client.is_user_authorized()
        print("session_path=", session_path)
        print("using_string_session=", bool((os.getenv("TELEGRAM_STRING_SESSION") or "").strip()))
        print("is_user_authorized=", ok)
        if ok:
            me = await client.get_me()
            print("me=", getattr(me, "username", None), "id=", getattr(me, "id", None))
        else:
            print("NOT authorized -> Run: python scripts/telegram_login.py (with same env) to authorize once.")
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
