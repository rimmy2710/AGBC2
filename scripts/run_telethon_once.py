#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import dataclasses
import inspect
import logging
import os
import sys
from datetime import datetime, timezone
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
      - keyword_rules: list   <-- keyword/topic/style mapping
      - styles: Dict[str, List[str]]
    """
    kw_list: List[str] = []
    kw_to_topic: Dict[str, str] = {}
    kw_to_style: Dict[str, str] = {}

    rules = getattr(cfg_admin, "keyword_rules", []) or []
    for r in rules:
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
    styles_clean: Dict[str, List[str]] = {}
    for k, v in styles.items():
        if isinstance(v, list):
            styles_clean[str(k)] = [str(x) for x in v if str(x).strip()]
        else:
            styles_clean[str(k)] = [str(v)]
    return _normalize_keywords(kw_list), kw_to_topic, kw_to_style, styles_clean


def _find_signature_from_examples(style_examples: List[str]) -> Optional[str]:
    """
    Nếu trong examples có nhắc tới signature “AGBC2 AI” thì ta append cứng.
    Bạn có thể đổi rule nhận diện tại đây.
    """
    blob = "\n".join(style_examples or [])
    if "AGBC2 AI" in blob:
        # signature chuẩn của bạn
        return "— AGBC2 AI"
    return None


def _maybe_append_signature(draft_text: str, style_examples: List[str]) -> str:
    sig = _find_signature_from_examples(style_examples)
    if not sig:
        return draft_text

    t = (draft_text or "").rstrip()
    if not t:
        return sig

    # đã có signature rồi thì thôi
    if sig in t:
        return t

    # đảm bảo cách dòng đẹp
    return f"{t}\n\n{sig}"


def _draft_to_sheets_item(
    d: Any,
    *,
    timestamp: str,
    channel: str,
    msg_id: int,
    keyword: str,
    fallback_title: str,
    fallback_link: str,
    raw_text: str,
    style_examples: List[str],
) -> Mapping[str, object]:
    """
    MUST match src/news_agent/pipeline/sheets.py expectations:
      timestamp, source, matched_keyword, title, summary_bullets, styled_draft, link, status, item_id
    """
    if dataclasses.is_dataclass(d):
        dct = dataclasses.asdict(d)
    elif isinstance(d, dict):
        dct = d
    else:
        dct = {k: getattr(d, k) for k in dir(d) if not k.startswith("_")}

    title = (dct.get("title") or dct.get("headline") or fallback_title or "").strip()

    summary = dct.get("summary_bullets") or dct.get("summary") or dct.get("summary_facts") or dct.get("bullets")
    if isinstance(summary, str):
        summary_bullets = [x.strip("-• \t") for x in summary.splitlines() if x.strip()]
    elif isinstance(summary, list):
        summary_bullets = [str(x).strip() for x in summary if str(x).strip()]
    else:
        summary_bullets = []

    styled_draft = (dct.get("draft") or dct.get("text") or dct.get("content") or "").strip()
    styled_draft = _maybe_append_signature(styled_draft, style_examples)

    link = (dct.get("link") or dct.get("source") or dct.get("url") or fallback_link or "").strip()

    item: Dict[str, object] = {
        "timestamp": timestamp,
        "source": "telegram",
        "matched_keyword": keyword,
        "title": title,
        "summary_bullets": summary_bullets,
        "styled_draft": styled_draft,
        "link": link,
        "status": "DRAFT",
        "item_id": f"{_safe_channel_slug(channel)}:{msg_id}",
        # extra debug field (không làm hại sheets.py)
        "raw": raw_text,
    }
    return item


def _build_sheets_client(sheet_id: str, tab_name: str):
    SheetsClient = getattr(sheets_mod, "SheetsClient", None)
    if SheetsClient is None:
        raise RuntimeError("news_agent.pipeline.sheets.SheetsClient not found")

    try:
        return SheetsClient(sheet_id=sheet_id, tab_name=tab_name)
    except TypeError:
        try:
            return SheetsClient(sheet_id, tab_name)
        except TypeError:
            c = SheetsClient(sheet_id)
            if hasattr(c, "tab_name"):
                setattr(c, "tab_name", tab_name)
            return c


def _append_items(items: List[Mapping[str, object]], sheet_id: str, tab_name: str) -> int:
    append_items = getattr(sheets_mod, "append_items", None)
    if append_items is None:
        raise RuntimeError("news_agent.pipeline.sheets.append_items not found")

    client = _build_sheets_client(sheet_id, tab_name)
    sig = inspect.signature(append_items)
    if "client" in sig.parameters:
        append_items(items, client=client)
    else:
        append_items(items)
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

    limit_per_channel = _int("LIMIT_PER_CHANNEL", 20)
    openai_enabled = _bool("OPENAI_ENABLED", False)
    max_ai_items = _int("MAX_AI_ITEMS", 1)

    tg_state_dir = Path(_env("TG_STATE_DIR", str(Path.home() / ".agbc2" / "tg_state")))

    # ---------- Load admin config ----------
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
        channels = [x.strip() for x in (_env("CHANNELS", "") or "").split(",") if x.strip()]
        keywords = _normalize_keywords([x for x in (_env("KEYWORDS", "") or "").split(",") if x.strip()])
        styles = {"telegram_casual": ["Tóm tắt nhanh, dễ đọc."]}

    channels = [c.strip() for c in channels if c.strip()]
    if not channels:
        log.warning("No channels configured")
        return 0

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

        write_draft = None
        if openai_enabled and max_ai_items > 0:
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
                now_iso = datetime.now(timezone.utc).isoformat()

                # Default non-AI item aligned with sheets.py schema
                base_row: Dict[str, object] = {
                    "timestamp": now_iso,
                    "source": "telegram",
                    "matched_keyword": kw,
                    "title": text[:120],
                    "summary_bullets": [text[:240]],
                    "styled_draft": text,
                    "link": link,
                    "status": "DRAFT",
                    "item_id": f"{_safe_channel_slug(ch)}:{msg.id}",
                    "raw": text,
                }

                if openai_enabled and write_draft and ai_calls < max_ai_items:
                    ai_calls += 1
                    try:
                        d = write_draft(
                            raw=text,
                            style_name=style_name,
                            style_examples=style_examples,
                            topic_or_keyword=topic,
                            link=link,
                        )
                        ai_item = _draft_to_sheets_item(
                            d,
                            timestamp=now_iso,
                            channel=ch,
                            msg_id=msg.id,
                            keyword=kw,
                            fallback_title=str(base_row["title"]),
                            fallback_link=link,
                            raw_text=text,
                            style_examples=style_examples,
                        )
                        drafted_rows.append(ai_item)
                        continue
                    except Exception as e:
                        log.exception("AI draft failed -> fallback to raw")
                        emsg = f"{e}"
                        if "429" in emsg or "RateLimit" in emsg or "rate limit" in emsg.lower():
                            log.warning("Rate limit detected -> disabling AI for rest of run")
                            openai_enabled = False
                            max_ai_items = 0
                        drafted_rows.append(base_row)
                        continue

                drafted_rows.append(base_row)

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
