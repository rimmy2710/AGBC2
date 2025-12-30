from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timezone
from typing import List, Tuple, Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message

from .normalize import NewsItem


def _read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def _state_path(state_dir: str, channel_key: str) -> str:
    os.makedirs(state_dir, exist_ok=True)
    safe = channel_key.replace("/", "_")
    return os.path.join(state_dir, f"{safe}.last_id")


def load_last_id(state_dir: str, channel_key: str) -> int:
    p = _state_path(state_dir, channel_key)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except FileNotFoundError:
        return 0
    except Exception:
        return 0


def save_last_id(state_dir: str, channel_key: str, last_id: int) -> None:
    p = _state_path(state_dir, channel_key)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(int(last_id)))
    os.replace(tmp, p)


@dataclass
class TelegramIngestConfig:
    api_id: int
    api_hash: str
    session_path: str
    channels_file: str
    tg_state_dir: str
    limit_per_channel: int = 200


class TelegramIngestor:
    def __init__(self, cfg: TelegramIngestConfig):
        self.cfg = cfg

    def read_channels(self) -> List[str]:
        return _read_lines(self.cfg.channels_file)

    async def fetch_new(self, channels_override: Optional[List[str]] = None) -> Tuple[List[NewsItem], int]:
        """
        Fetch new Telegram messages as NewsItem.

        channels_override:
          - If provided (non-empty list), use it instead of reading channels from cfg.channels_file.
          - This supports admin-config-driven channel lists without needing to write files.
        """
        channels = channels_override if channels_override else self.read_channels()
        if not channels:
            return [], 0

        session_str = os.getenv("TELEGRAM_STRING_SESSION", "").strip()
        if session_str:
            client = TelegramClient(StringSession(session_str), self.cfg.api_id, self.cfg.api_hash)
        else:
            client = TelegramClient(self.cfg.session_path, self.cfg.api_id, self.cfg.api_hash)


        items: List[NewsItem] = []
        channels_processed = 0

        async with client:
            if not await client.is_user_authorized():
                raise RuntimeError(
                    "Telegram not authorized. Set TELEGRAM_STRING_SESSION in Codespaces secrets, "
                    "or run scripts/telegram_login.py once (not recommended for CI)."
                )
            for ch in channels:
                channels_processed += 1
                last_id = load_last_id(self.cfg.tg_state_dir, ch)

                new_msgs: List[Message] = []
                async for msg in client.iter_messages(
                    entity=ch,
                    min_id=last_id,
                    limit=self.cfg.limit_per_channel,
                ):
                    if not getattr(msg, "id", None):
                        continue
                    if msg.id <= last_id:
                        continue
                    text = (msg.message or "").strip()
                    if not text:
                        continue
                    new_msgs.append(msg)

                if not new_msgs:
                    continue

                new_msgs.sort(key=lambda m: m.id)

                max_id = last_id
                for msg in new_msgs:
                    max_id = max(max_id, msg.id)
                    dt = msg.date
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    text = (msg.message or "").strip()
                    item_id = f"tg:{ch}:{msg.id}"
                    title = NewsItem.make_title(text, fallback=f"Telegram update from {ch}")

                    link = ""
                    if ch.startswith("@"):
                        link = f"https://t.me/{ch[1:]}/{msg.id}"
                    elif "t.me/" in ch:
                        base = ch.rstrip("/")
                        link = f"{base}/{msg.id}"

                    items.append(
                        NewsItem(
                            item_id=item_id,
                            time_iso=NewsItem.iso(dt),
                            source=ch,
                            topic="",
                            title=title,
                            content=text,
                            link=link,
                        )
                    )

                save_last_id(self.cfg.tg_state_dir, ch, max_id)

        return items, channels_processed
