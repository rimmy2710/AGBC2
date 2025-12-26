from __future__ import annotations

import asyncio
import os

from telethon import TelegramClient


async def main() -> None:
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_path = os.environ["TELEGRAM_SESSION_PATH"]

    print("session_path=", session_path)

    client = TelegramClient(session_path, api_id, api_hash)

    # IMPORTANT: connect() only, no start() prompt.
    await client.connect()
    try:
        authorized = await client.is_user_authorized()
        print("is_user_authorized=", authorized)
        if authorized:
            me = await client.get_me()
            print("me=", (me.username or me.first_name), "id=", me.id)
        else:
            print("NOT authorized -> session exists but isn't logged in under current API_ID/HASH.")
            print("Run: python scripts/telegram_login.py (with same env) to authorize once.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
