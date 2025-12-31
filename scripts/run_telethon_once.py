#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import dataclasses
import inspect
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

# ---------------------------------------------------------------------
# Ensure src/ is on PYTHONPATH (Codespaces + Actions)
# ---------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from news_agent.pipeline.admin_config import load_admin_config
from news_agent.pipeline.telethon_client import build_telegram_client
from news_agent.pipeline import sheets as sheets_mod

log = logging.getLogger("run_telethon_once")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v


def _must(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _int(name: str, default: int) -> int:
    v = _env(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    v = _env(name)
    if v is None:
        return default
    return v.strip() in ("1", "true", "True", "yes", "YES", "on", "ON")


def _safe_channel_slug(ch: str) -> str:
    ch = ch.strip()
    return ch[1:] if ch.startswith("@") else ch


def _msg_link(channel: str, msg_id: int) -> str:
    # For public channels, t.me/<channel>/<id> usually works
    return f"https://t.me/{_safe_channel_slug(channel)}/{msg_id}"


def _load_last_id(state_dir: Path, channel: str) -> int:
    p = state_dir / f"{channel}.last_id"
    if not p.exists():
        return 0
    try:
        return int(p.read_text().strip() or "0")
    except Exception:
        return 0


def _save_last_id(state_dir: Path, channel: str, last_id: int) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / f"{channel}.last_id"
    p.write_text(str(int(last_id)))


def _normalize_keywords(xs: Iterable[str]) -> List[str]:
    out: List[str] = []
    for x in xs:
        x = (x or "").strip().lower()
        if x:
            out.append(x)
    return out


def _match_any_keyword(text: str, keywords: List[str]) -> Optional[str]:
    if not keywords:
        return None
    t = (text or "").lower()
    for kw in keywords:
        if kw and kw in t:
            return kw
    return None


def _extract_admin_rules(cfg_admin: Any) -> Tuple[List[str], Dict[str, str], Dict[str, str], Dict[str, List[str]]]:
    """
    admin_config.AdminConfig currently exposes:
      - channels: List[str]
      - keyword_rules: (list)  <-- contains keyword/topic/style mapping
      - styles: Dict[str, List[str]]
    We must NOT assume cfg_admin.keywords exists.
    """
    kw_list: List[str] = []
    kw_to_topic: Dict[str, str] = {}
    kw_to_style: Dict[str, str] = {}

    rules = getattr(cfg_admin, "keyword_rules", []) or []
    for r in rules:
        # rule can be dict-like or object-like
        if isinstance(r, dict):
            kw = (r.get("keyword") or r.get("kw") or r.get("term") or "").strip()
            topic = (r.get("topic") or r.get("category") or "").strip()
            style = (r.get("style") or r.get("style_name") or "").strip()
        else:
            kw = (getattr(r, "keyword", None) or getattr(r, "kw", None) or getattr(r, "term", None) or "").strip()
            topic = (getattr(r, "topic", None) or getattr(r, "category", None) or "").strip()
            style = (getattr(r, "style", None) or getattr(r, "style_name", None) or "").strip()

        if not kw:
            continue
        kw_l = kw.lower()
        kw_list.append(kw_l)
        if topic:
            kw_to_topic[kw_l] = topic
        if style:
            kw_to_style[kw_l] = style

    styles = getattr(cfg_admin, "styles", {}) or {}
    # Ensure style examples are list[str]
    styles_clean: Dict[str, List[str]] = {}
    for k, v in styles.items():
        if isinstance(v, list):
            styles_clean[str(k)] = [str(x) for x in v if str(x).strip()]
        else:
            styles_clean[str(k)] = [str(v)]
    return _normalize_keywords(kw_list), kw_to_topic, kw_to_style, styles_clean


def _draft_to_mapping(d: Any, *, fallback_title: str, fallback_link: str, keyword: str, style_name: str) -> Mapping[str, object]:
    """
    sheets.append_items expects Iterable[Mapping[str, object]].
    We'll produce a mapping with keys that sheets.py is known to read:
      - title
      - summary_bullets
      - draft
      - link
      - keyword
      - style
      - raw
    """
    data: Dict[str, object] = {}

    if dataclasses.is_dataclass(d):
        dct = dataclasses.asdict(d)
    elif isinstance(d, dict):
        dct = d
    else:
        # best-effort
        dct = {k: getattr(d, k) for k in dir(d) if not k.startswith("_")}

    # Common fields we may get from Draft
    title = dct.get("title") or dct.get("headline") or fallback_title
    draft = dct.get("draft") or dct.get("text") or dct.get("content") or ""
    summary = dct.get("summary_bullets") or dct.get("summary") or dct.get("summary_facts") or dct.get("bullets")

    if isinstance(summary, str):
        # split into bullets lightly
        summary_bullets = [x.strip("-• \t") for x in summary.splitlines() if x.strip()]
    elif isinstance(summary, list):
        summary_bullets = [str(x).strip() for x in summary if str(x).strip()]
    else:
        summary_bullets = []

    link = dct.get("link") or dct.get("source") or dct.get("url") or fallback_link
    raw = dct.get("raw") or dct.get("input") or ""

    data["title"] = str(title)
    data["summary_bullets"] = summary_bullets
    data["draft"] = str(draft)
    data["link"] = str(link)
    data["keyword"] = str(keyword)
    data["style"] = str(style_name)
    data["raw"] = str(raw)

    return data


def _build_sheets_client(sheet_id: str, tab_name: str):
    SheetsClient = getattr(sheets_mod, "SheetsClient", None)
    if SheetsClient is None:
        raise RuntimeError("news_agent.pipeline.sheets.SheetsClient not found")

    # Try common ctor shapes
    try:
        return SheetsClient(sheet_id=sheet_id, tab_name=tab_name)
    except TypeError:
        try:
            return SheetsClient(sheet_id, tab_name)
        except TypeError:
            # last resort: sheet_id only, tab name set via attribute
            c = SheetsClient(sheet_id)
            if hasattr(c, "tab_name"):
                setattr(c, "tab_name", tab_name)
            return c


def _append_items(items: List[Mapping[str, object]], sheet_id: str, tab_name: str) -> int:
    append_items = getattr(sheets_mod, "append_items", None)
    if append_items is None:
        raise RuntimeError("news_agent.pipeline.sheets.append_items not found")

    client = _build_sheets_client(sheet_id, tab_name)

    # Signature known: append_items(items, client=None)
    sig = inspect.signature(append_items)
    if "client" in sig.parameters:
        append_items(items, client=client)
    else:
        append_items(items)

    # append_items returns None; we return count for logs
    return len(items)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
async def run_once() -> int:
    google_sheet_id = _must("GOOGLE_SHEET_ID")
    google_sheet_tab = _env("GOOGLE_SHEET_TAB", "AGBC2 – News Draft") or "AGBC2 – News Draft"

    telegram_api_id = int(_must("TELEGRAM_API_ID"))
    telegram_api_hash = _must("TELEGRAM_API_HASH")
    session_path = _env("TELEGRAM_SESSION_PATH", str(Path.home() / ".agbc2" / "secrets" / "telegram.session"))
    # build_telegram_client reads TELEGRAM_STRING_SESSION itself

    limit_per_channel = _int("LIMIT_PER_CHANNEL", 20)
    openai_enabled = _bool("OPENAI_ENABLED", False)
    max_ai_items = _int("MAX_AI_ITEMS", 1)

    tg_state_dir = Path(_env("TG_STATE_DIR", str(Path.home() / ".agbc2" / "tg_state")))

    # ---------- Load admin config (preferred) ----------
    channels: List[str] = []
    keywords: List[str] = []
    kw_to_topic: Dict[str, str] = {}
    kw_to_style: Dict[str, str] = {}
    styles: Dict[str, List[str]] = {}
    admin = False

    admin_sheet_id = _env("ADMIN_CONFIG_SHEET_ID")
    if admin_sheet_id:
        cfg_admin = load_admin_config(admin_sheet_id, channels_tab="channels", keywords_tab="keywords", styles_tab="styles")
        channels = list(getattr(cfg_admin, "channels", []) or [])
        keywords, kw_to_topic, kw_to_style, styles = _extract_admin_rules(cfg_admin)
        admin = True
    else:
        # env fallback
        channels = [x.strip() for x in (_env("CHANNELS", "") or "").split(",") if x.strip()]
        keywords = _normalize_keywords([x for x in (_env("KEYWORDS", "") or "").split(",") if x.strip()])
        styles = {"telegram_casual": ["Tóm tắt nhanh, dễ đọc."]}

    channels = [c.strip() for c in channels if c.strip()]
    if not channels:
        log.warning("No channels configured")
        return 0

    # ---------- Telethon ingest ----------
    client = build_telegram_client(telegram_api_id, telegram_api_hash, session_path or "")
    await client.connect()
    try:
        ok = await client.is_user_authorized()
        if not ok:
            raise RuntimeError("Telegram not authorized")

        drafted_rows: List[Mapping[str, object]] = []
        channels_processed = 0
        fetched = 0
        ai_calls = 0

        # Lazy import AI writer only if needed (avoid import mismatch breaking non-AI runs)
        write_draft = None
        if openai_enabled:
            try:
                from news_agent.pipeline.ai_writer import write_draft as _write_draft
                write_draft = _write_draft
            except Exception:
                log.exception("AI import failed -> continue without AI")
                write_draft = None
                openai_enabled = False

        for ch in channels:
            channels_processed += 1
            last_id = _load_last_id(tg_state_dir, ch)
            max_seen_id = last_id

            # Pull newest first; we will filter + track max id
            async for msg in client.iter_messages(ch, min_id=last_id, limit=limit_per_channel):
                text = (msg.message or "").strip()
                if not text:
                    continue

                if msg.id and msg.id > max_seen_id:
                    max_seen_id = msg.id

                matched_kw = _match_any_keyword(text, keywords)
                if keywords and not matched_kw:
                    continue

                fetched += 1
                kw = matched_kw or (keywords[0] if keywords else "general")
                topic = kw_to_topic.get(kw, kw)
                style_name = kw_to_style.get(kw, "telegram_casual")
                style_examples = styles.get(style_name, styles.get("telegram_casual", ["Tóm tắt nhanh."]))
                link = _msg_link(ch, msg.id)

                # Default non-AI row
                base_row: Dict[str, object] = {
                    "title": text[:120],
                    "summary_bullets": [text[:240]],
                    "draft": text,
                    "link": link,
                    "keyword": kw,
                    "style": style_name,
                    "raw": text,
                }

                if openai_enabled and write_draft and ai_calls < max_ai_items:
                    ai_calls += 1  # count attempts to call AI
                    try:
                        d = write_draft(
                            raw=text,
                            style_name=style_name,
                            style_examples=style_examples,
                            topic_or_keyword=topic,
                            link=link,
                        )
                        row = _draft_to_mapping(
                            d,
                            fallback_title=str(base_row["title"]),
                            fallback_link=link,
                            keyword=kw,
                            style_name=style_name,
                        )
                        drafted_rows.append(row)
                        continue
                    except Exception:
                        log.exception("AI draft failed -> fallback to raw")
                        drafted_rows.append(base_row)
                        continue

                drafted_rows.append(base_row)

            # persist state per channel
            if max_seen_id > last_id:
                _save_last_id(tg_state_dir, ch, max_seen_id)

        if not drafted_rows:
            log.info(
                "channels_processed=%d fetched=0 new_items=0 appended=0 keywords=%d admin=%s",
                channels_processed,
                len(keywords),
                admin,
            )
            return 0

        appended = _append_items(drafted_rows, sheet_id=google_sheet_id, tab_name=google_sheet_tab)

        log.info(
            "channels_processed=%d fetched=%d new_items=%d appended=%d keywords=%d admin=%s tab=%s ai=%s ai_calls=%d max_ai_items=%d",
            channels_processed,
            fetched,
            len(drafted_rows),
            appended,
            len(keywords),
            admin,
            google_sheet_tab,
            openai_enabled,
            ai_calls,
            max_ai_items,
        )
        return 0

    finally:
        await client.disconnect()


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
