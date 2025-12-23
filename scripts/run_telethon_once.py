from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys

from dotenv import load_dotenv

from news_agent.pipeline.ai_writer import write_draft
from news_agent.pipeline.dedup import DedupStore
from news_agent.pipeline.filter import filter_items, load_keywords
from news_agent.pipeline.ingest_telethon import TelegramIngestConfig, TelegramIngestor
from news_agent.pipeline.sheets import SheetsClient, append_items
from news_agent.pipeline.style_library import load_style_examples, resolve_style_dir


def _must_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _parse_iso_datetime(value: str) -> dt.datetime:
    # NewsItem.iso() returns timezone-aware ISO; handle common variants.
    v = (value or "").strip()
    if not v:
        return dt.datetime.utcnow()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(v)
    except Exception:
        return dt.datetime.utcnow()


def main() -> int:
    load_dotenv()

    api_id = int(_must_env("TELEGRAM_API_ID"))
    api_hash = _must_env("TELEGRAM_API_HASH")
    session_path = _must_env("TELEGRAM_SESSION_PATH")

    # Sheets (gspread uses GOOGLE_APPLICATION_CREDENTIALS implicitly)
    _must_env("GOOGLE_SHEET_ID")
    _must_env("GOOGLE_APPLICATION_CREDENTIALS")
    sheet_tab = os.getenv("GOOGLE_SHEET_TAB", "Sheet1").strip() or "Sheet1"

    state_dir = os.getenv("STATE_DIR", "./storage").strip() or "./storage"
    channels_file = os.getenv("TELEGRAM_CHANNELS_FILE", os.path.join(state_dir, "telegram_channels.txt")).strip()

    tg_state_dir = os.path.join(state_dir, "tg_state")
    dedup_path = os.path.join(state_dir, "dedup.json")

    # Phase-1 config
    keywords_path = os.getenv("KEYWORDS_FILE", os.path.join(state_dir, "keywords.txt")).strip()
    style_name = os.getenv("STYLE_NAME", "telegram_casual").strip() or "telegram_casual"
    style_dir = resolve_style_dir(os.getenv("STYLE_LIBRARY_DIR"))
    style_max_examples = int(os.getenv("STYLE_MAX_EXAMPLES", "10"))

    ing = TelegramIngestor(
        TelegramIngestConfig(
            api_id=api_id,
            api_hash=api_hash,
            session_path=session_path,
            channels_file=channels_file,
            tg_state_dir=tg_state_dir,
            limit_per_channel=int(os.getenv("TG_LIMIT_PER_CHANNEL", "200")),
        )
    )

    items, channels_processed = asyncio.run(ing.fetch_new())

    # Dedup first
    store = DedupStore(path=dedup_path, max_items=int(os.getenv("DEDUP_MAX_ITEMS", "50000")))
    is_new = store.filter_new([it.item_id for it in items])
    items = [it for it in items if is_new.get(it.item_id, False)]

    # Load keywords and filter
    keywords = load_keywords(keywords_path)
    if not keywords:
        # strict mode by default
        print(
            f"channels_processed={channels_processed} fetched={len(is_new)} new_items=0 appended=0 "
            f"keywords=0 style={style_name} (no keywords configured; strict drop)",
            flush=True,
        )
        return 0

    dict_items = [
        {"item_id": it.item_id, "title": it.title, "content": it.content, "source": it.source, "link": it.link}
        for it in items
    ]
    qualified, match_map = filter_items(dict_items, keywords)
    qualified_ids = {q.get("item_id") for q in qualified}
    items = [it for it in items if it.item_id in qualified_ids]

    # Load style examples once
    style_examples = load_style_examples(style_dir, style_name, max_examples=style_max_examples)

    # Build sheet entries expected by news_agent.pipeline.sheets.append_items
    sheet_items = []
    for it in items:
        matched_kw = match_map.get(it.item_id, "")
        out = write_draft(
            raw=it.content,
            style_name=style_name,
            style_examples=style_examples,
            topic_or_keyword=matched_kw,
            link=it.link,
        )

        # summary bullets as list (remove leading "- " if present)
        bullets = []
        for ln in (out.summary_facts or "").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            bullets.append(ln[2:].strip() if ln.startswith("- ") else ln)

        sheet_items.append(
            {
                "timestamp": _parse_iso_datetime(it.time_iso),
                "source": it.source,
                "matched_keyword": matched_kw,
                "title": out.title,
                "summary_bullets": bullets,
                "styled_draft": out.draft,
                "link": it.link,
                "status": "DRAFT",
                "item_id": it.item_id,
            }
        )

    client = SheetsClient(tab_name=sheet_tab)
    append_items(sheet_items, client=client)

    appended = len(sheet_items)
    print(
        f"channels_processed={channels_processed} fetched={len(is_new)} new_items={len(items)} appended={appended} "
        f"keywords={len(keywords)} style={style_name}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        raise
