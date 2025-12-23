"""Google Sheets writer for news agent pipeline."""
from __future__ import annotations

import datetime as dt
import os
from typing import Iterable, List, Mapping, Sequence

try:
    import gspread
except ImportError:  # pragma: no cover - optional dependency
    gspread = None  # type: ignore


class SheetsClient:
    """Wrapper around gspread with graceful degradation when creds are missing."""

    def __init__(self, sheet_id: str | None = None, tab_name: str | None = None):
        self.sheet_id = sheet_id or os.environ.get("GOOGLE_SHEET_ID")
        self.tab_name = tab_name or os.environ.get("GOOGLE_SHEET_TAB", "Sheet1")

    def _open_sheet(self):
        if gspread is None:
            raise RuntimeError("gspread is not installed; cannot write to Google Sheets")
        if not self.sheet_id:
            raise RuntimeError("GOOGLE_SHEET_ID is not configured")
        client = gspread.service_account()
        spreadsheet = client.open_by_key(self.sheet_id)
        return spreadsheet.worksheet(self.tab_name)

    def append_rows(self, rows: Sequence[Sequence[object]]) -> None:
        worksheet = self._open_sheet()
        worksheet.append_rows(rows, value_input_option="RAW")


HEADER = [
    "Time",
    "Source",
    "Topic/Keyword",
    "Title",
    "Summary (facts)",
    "Draft (styled)",
    "Link",
    "Status",
    "item_id",
]


def _format_timestamp(timestamp: object | None) -> str:
    if isinstance(timestamp, (int, float)):
        return dt.datetime.utcfromtimestamp(float(timestamp)).isoformat()
    if isinstance(timestamp, dt.datetime):
        return timestamp.isoformat()
    return dt.datetime.utcnow().isoformat()


def _format_entry(item: Mapping[str, object]) -> List[object]:
    summary_field = item.get("summary_bullets")
    summary = " \n".join(summary_field) if isinstance(summary_field, (list, tuple)) else summary_field or ""

    return [
        _format_timestamp(item.get("timestamp")),
        item.get("source", "telegram"),
        item.get("matched_keyword", ""),
        item.get("title", ""),
        summary,
        item.get("styled_draft", ""),
        item.get("link", ""),
        item.get("status", "DRAFT"),
        item.get("item_id", ""),
    ]


def append_items(items: Iterable[Mapping[str, object]], client: SheetsClient | None = None) -> None:
    client = client or SheetsClient()
    rows = [_format_entry(item) for item in items]
    client.append_rows(rows)
