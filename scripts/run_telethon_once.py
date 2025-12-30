#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure src/ is on PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_telethon_once")


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def _must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _normalize_keyword_rules(keyword_rules: Any) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    """
    AdminConfig.keyword_rules can be list of dicts/tuples/objects depending on version.
    We extract:
      - keywords: [str]
      - kw_to_topic: {kw: topic}
      - kw_to_style: {kw: style}
    """
    keywords: List[str] = []
    kw_to_topic: Dict[str, str] = {}
    kw_to_style: Dict[str, str] = {}

    if not keyword_rules:
        return keywords, kw_to_topic, kw_to_style

    for r in keyword_rules:
        kw = None
        topic = None
        style = None

        if isinstance(r, dict):
            kw = r.get("keyword") or r.get("kw") or r.get("term")
            topic = r.get("topic")
            style = r.get("style")
        elif isinstance(r, (list, tuple)):
            # heuristic: (keyword, topic, style) or (keyword, topic) etc.
            if len(r) >= 1:
                kw = r[0]
            if len(r) >= 2:
                topic = r[1]
            if len(r) >= 3:
                style = r[2]
        else:
            # object-like
            kw = getattr(r, "keyword", None) or getattr(r, "kw", None) or getattr(r, "term", None)
            topic = getattr(r, "topic", None)
            style = getattr(r, "style", None)

        if not kw:
            continue

        kw_s = str(kw).strip().lower()
        if not kw_s:
            continue

        keywords.append(kw_s)
        if topic:
            kw_to_topic[kw_s] = str(topic).strip()
        if style:
            kw_to_style[kw_s] = str(style).strip()

    # dedup keep order
    seen = set()
    deduped: List[str] = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            deduped.append(k)

    return deduped, kw_to_topic, kw_to_style


async def run_once() -> int:
    # ---- ENV ----
    google_sheet_id = _must_env("GOOGLE_SHEET_ID")
    google_sheet_tab = _env("GOOGLE_SHEET_TAB", "AGBC2 – News Draft") or "AGBC2 – News Draft"

    admin_enabled = (_env("ADMIN_CONFIG_ENABLED", "1") == "1")
    admin_sheet_id = _env("ADMIN_CONFIG_SHEET_ID")

    api_id = int(_must_env("TELEGRAM_API_ID"))
    api_hash = _must_env("TELEGRAM_API_HASH")
    session_path = _env("TELEGRAM_SESSION_PATH", os.path.expanduser("~/.agbc2/secrets/telegram.session")) or ""

    limit_per_channel = int(_env("LIMIT_PER_CHANNEL", "20") or "20")
    openai_enabled = (_env("OPENAI_ENABLED", "0") == "1")

    # ---- LOAD ADMIN CONFIG ----
    channels: List[str] = []
    keywords: List[str] = []
    kw_to_topic: Dict[str, str] = {}
    kw_to_style: Dict[str, str] = {}
    styles: Dict[str, Any] = {}
    admin = False

    if admin_enabled:
        if not admin_sheet_id:
            raise RuntimeError("ADMIN_CONFIG_ENABLED=1 but ADMIN_CONFIG_SHEET_ID missing")

        from news_agent.pipeline.admin_config import load_admin_config

        cfg = load_admin_config(
            admin_sheet_id,
            channels_tab="channels",
            keywords_tab="keywords",
            styles_tab="styles",
        )

        channels = list(getattr(cfg, "channels", []) or [])
        styles = dict(getattr(cfg, "styles", {}) or {})

        keyword_rules = getattr(cfg, "keyword_rules", None)
        keywords, kw_to_topic, kw_to_style = _normalize_keyword_rules(keyword_rules)

        admin = True
    else:
        # manual fallback if admin disabled
        channels = [c.strip() for c in (_env("CHANNELS", "") or "").split(",") if c.strip()]
        keywords = [k.strip().lower() for k in (_env("KEYWORDS", "") or "").split(",") if k.strip()]

    channels = [c.strip() for c in channels if str(c).strip()]
    keywords = [k.strip().lower() for k in keywords if str(k).strip()]

    if not channels:
        log.warning("No channels configured")
        return 0

    # ---- TELEGRAM INGEST ----
    from news_agent.pipeline.ingest_telethon import TelegramIngestConfig, TelegramIngestor

    fields = {f.name for f in dataclasses.fields(TelegramIngestConfig)}
    cfg_kwargs: Dict[str, Any] = {}

    # required-ish across versions
    if "api_id" in fields:
        cfg_kwargs["api_id"] = api_id
    if "api_hash" in fields:
        cfg_kwargs["api_hash"] = api_hash
    if "session_path" in fields:
        cfg_kwargs["session_path"] = session_path
    if "limit_per_channel" in fields:
        cfg_kwargs["limit_per_channel"] = limit_per_channel

    # older versions require these two:
    if "channels_file" in fields:
        cfg_kwargs["channels_file"] = _env("CHANNELS_FILE", str(ROOT / "storage" / "channels.txt"))
    if "tg_state_dir" in fields:
        cfg_kwargs["tg_state_dir"] = _env("TG_STATE_DIR", os.path.expanduser("~/.agbc2/tg_state"))

    ing_cfg = TelegramIngestConfig(**cfg_kwargs)
    ingestor = TelegramIngestor(ing_cfg)

    # ingestor supports channels_override (you already patched it)
    items, channels_processed = await ingestor.fetch_new(channels_override=channels)
    fetched = len(items)

    if fetched == 0:
        log.info(
            "channels_processed=%d fetched=0 new_items=0 appended=0 keywords=%d admin=%s",
            channels_processed,
            len(keywords),
            admin,
        )
        return 0

    # ---- AI REWRITE (safe adapter) ----
    if openai_enabled:
        # Prefer ai_writer facade (it can fallback)
        try:
            from news_agent.pipeline.ai_writer import rewrite_news_items as _rewrite
            items = _rewrite(items, kw_to_topic=kw_to_topic, kw_to_style=kw_to_style, styles=styles)
        except Exception:
            log.exception("AI rewrite failed -> continue without rewrite")

    # ---- OUTPUT TO SHEET ----
    from news_agent.pipeline.sheets import SheetClient

    sheet = SheetClient(sheet_id=google_sheet_id, tab_name=google_sheet_tab)
    rows = [it.to_row() for it in items]
    appended = sheet.append_rows(rows)

    log.info(
        "channels_processed=%d fetched=%d new_items=%d appended=%d keywords=%d admin=%s",
        channels_processed,
        fetched,
        fetched,
        appended,
        len(keywords),
        admin,
    )
    return 0


def main() -> int:
    try:
        return asyncio.run(run_once())
    except KeyboardInterrupt:
        return 130
    except Exception:
        log.exception("Fatal error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
