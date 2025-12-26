from __future__ import annotations

import asyncio
import os

from telethon import TelegramClient


async def main() -> None:
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_path = os.environ.get("TELEGRAM_SESSION_PATH", "secrets/telegram.session")

    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()  # prompts for phone/code/password if needed
    me = await client.get_me()
    print(f"Logged in as: {me.username or me.first_name} (id={me.id})")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
