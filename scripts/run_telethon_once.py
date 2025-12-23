"""One-shot runner to ingest, deduplicate, filter, write, and export to Sheets."""
from __future__ import annotations

import logging
import os
from typing import List, Mapping

from src.news_agent.pipeline import ai_writer, filter as keyword_filter, sheets, style_library

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def _load_ingested_messages() -> List[Mapping[str, str]]:
    try:
        from ingest_telethon import collect_messages  # type: ignore
    except ImportError:
        LOGGER.warning("ingest_telethon.collect_messages not found; returning sample payload")
        return [
            {
                "item_id": "demo-1",
                "text": "BTC breaks above $70k as ETF inflows accelerate.",
                "timestamp": None,
                "source": "telegram",
                "link": "https://t.me/example/1",
            },
            {
                "item_id": "demo-2",
                "text": "Random off-topic chatter without signal.",
                "timestamp": None,
                "source": "telegram",
                "link": "https://t.me/example/2",
            },
        ]

    return collect_messages()


def _deduplicate(items: List[Mapping[str, str]]) -> List[Mapping[str, str]]:
    try:
        from dedup import deduplicate_items  # type: ignore
    except ImportError:
        LOGGER.warning("dedup.deduplicate_items not found; skipping dedup")
        return items
    return deduplicate_items(items)


def main() -> None:
    LOGGER.info("Starting one-shot run")
    raw_items = _load_ingested_messages()
    deduped_items = _deduplicate(raw_items)

    keywords = keyword_filter.load_keywords(os.environ.get("KEYWORDS_FILE", ""))
    filtered_items = keyword_filter.filter_items(deduped_items, keywords)

    style_name = os.environ.get("STYLE_NAME", "telegram_casual")
    style_samples = style_library.load_style_samples(style_name)

    enriched_items = []
    for item in filtered_items:
        composed = ai_writer.compose_draft(item, style_samples, style_name)
        enriched = {
            **item,
            **composed,
            "status": item.get("status", "DRAFT"),
        }
        enriched_items.append(enriched)
    if not enriched_items:
        LOGGER.info("No items qualified after filtering")
        return

    try:
        sheets.append_items(enriched_items)
        LOGGER.info("Appended %d items to sheet", len(enriched_items))
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to append items to sheet: %s", exc)


if __name__ == "__main__":
    main()
