from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class NewsItem:
    item_id: str
    time_iso: str
    source: str
    topic: str
    title: str
    content: str
    link: str = ""

    @staticmethod
    def iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def make_title(text: str, fallback: str = "") -> str:
        t = (text or "").strip()
        if not t:
            return fallback
        first_line = t.splitlines()[0].strip()
        if len(first_line) > 140:
            return first_line[:137] + "..."
        return first_line
