from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Dict, Iterable, List, Mapping, Tuple

from dotenv import load_dotenv

from news_agent.pipeline.ai_writer import write_draft
from news_agent.pipeline.admin_config import build_keyword_maps, load_admin_config
from news_agent.pipeline.dedup import DedupStore
from news_agent.pipeline.filter import filter_items, load_keywords
from news_agent.pipeline.ingest_telethon import TelegramIngestConfig, TelegramIngestor
from news_agent.pipeline.sheets import SheetsClient, append_items
from news_agent.pipeline.style_library import load_style_examples, resolve_style_dir


# =========================
# helpers
# =========================
def _must_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _newsitem_item_id(it: object) -> str:
    v = getattr(it, "item_id", "") or ""
    return str(v)


def _newsitem_to_mapping(it: object) -> Dict[str, object]:
    """
    Your NewsItem in this repo version may NOT have to_dict().
    We convert by reading common attributes safely.
    """
    out: Dict[str, object] = {}
    for k in (
        "item_id",
        "timestamp",
        "source",
        "channel",
        "title",
        "text",
        "content",
        "link",
        "raw",
    ):
        v = getattr(it, k, None)
        if v is not None and v != "":
            out[k] = v

    # Normalize content field for writer/filter
    if "content" not in out:
        if "text" in out:
            out["content"] = out.get("text", "")
        elif "raw" in out:
            out["content"] = out.get("raw", "")
        else:
            out["content"] = ""

    # Provide defaults
    out.setdefault("source", "telegram")
    out.setdefault("link", "")
    out.setdefault("title", "")
    out.setdefault("item_id", _newsitem_item_id(it))
    return out


def _dedup_load_json(path: str) -> Dict[str, int]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return {str(k): int(v) if isinstance(v, (int, bool)) else 1 for k, v in raw.items()}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}


def _dedup_save_json(path: str, data: Dict[str, int]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _dedup_load(dedup: object, dedup_path: str) -> Dict[str, int]:
    # Prefer DedupStore.load() if it exists and returns dict
    if hasattr(dedup, "load"):
        try:
            data = dedup.load()  # type: ignore[attr-defined]
            if isinstance(data, dict):
                return {str(k): int(v) if isinstance(v, (int, bool)) else 1 for k, v in data.items()}
        except Exception:
            pass
    return _dedup_load_json(dedup_path)


def _dedup_save(dedup: object, dedup_path: str, data: Dict[str, int]) -> None:
    """
    Your DedupStore.save REQUIRES (data).
    We'll call save(data) if possible; fallback to writing JSON ourselves.
    """
    if hasattr(dedup, "save"):
        try:
            dedup.save(data)  # type: ignore[attr-defined]
            return
        except TypeError:
            # Wrong signature / older version
            pass
        except Exception:
            pass
    _dedup_save_json(dedup_path, data)


def _load_admin_runtime() -> Tuple[List[str], List[str], Dict[str, str], Dict[str, str], Dict[str, List[str]]]:
    cfg = load_admin_config(
        sheet_id=_must_env("ADMIN_CONFIG_SHEET_ID"),
        channels_tab=os.getenv("ADMIN_CHANNELS_TAB", "channels"),
        keywords_tab=os.getenv("ADMIN_KEYWORDS_TAB", "keywords"),
        styles_tab=os.getenv("ADMIN_STYLES_TAB", "styles"),
        max_style_examples=int(os.getenv("STYLE_MAX_EXAMPLES", "10")),
    )
    keywords, kw_to_topic, kw_to_style = build_keyword_maps(cfg.keyword_rules)
    return cfg.channels, keywords, kw_to_topic, kw_to_style, cfg.styles


def _unwrap_filter_result(res) -> Tuple[List[Dict[str, object]], Dict[str, str]]:
    """
    filter_items has two possible implementations in this repo history:
    - returns (qualified_items, match_map)
    - returns qualified_items (and embeds matched_keyword)
    """
    if isinstance(res, tuple) and len(res) == 2:
        qualified, match_map = res
        qualified2 = [dict(x) for x in qualified]
        match_map2 = {str(k): str(v) for k, v in (match_map or {}).items()}
        return qualified2, match_map2

    qualified_list = res if isinstance(res, list) else []
    qualified2 = [dict(x) for x in qualified_list]
    match_map2: Dict[str, str] = {}
    for it in qualified2:
        item_id = str(it.get("item_id", "") or "")
        mk = str(it.get("matched_keyword", "") or "")
        if item_id and mk:
            match_map2[item_id] = mk
    return qualified2, match_map2


# =========================
# main
# =========================
def main() -> int:
    load_dotenv()

    # required env
    api_id = int(_must_env("TELEGRAM_API_ID"))
    api_hash = _must_env("TELEGRAM_API_HASH")
    session_path = _must_env("TELEGRAM_SESSION_PATH")

    sheet_id = _must_env("GOOGLE_SHEET_ID")
    _must_env("GOOGLE_APPLICATION_CREDENTIALS")  # gspread reads env or default
    tab = os.getenv("GOOGLE_SHEET_TAB", "AGBC2 – News Draft")

    state_dir = os.getenv("STATE_DIR", "storage")
    os.makedirs(state_dir, exist_ok=True)

    admin_enabled = os.getenv("ADMIN_CONFIG_ENABLED", "").strip().lower() in ("1", "true", "yes", "y", "on")

    # admin config (optional)
    if admin_enabled:
        channels, keywords, kw_to_topic, kw_to_style, styles_dict = _load_admin_runtime()
        channels_override = channels
    else:
        keywords = load_keywords()
        kw_to_topic = {}
        kw_to_style = {}
        styles_dict = {}
        channels_override = None

    # ingest
    cfg = TelegramIngestConfig(
        api_id=api_id,
        api_hash=api_hash,
        session_path=session_path,
        channels_file=os.path.join(state_dir, "telegram_channels.txt"),
        tg_state_dir=os.path.join(state_dir, "tg_state"),
        limit_per_channel=int(os.getenv("LIMIT_PER_CHANNEL", "50")),
    )
    ing = TelegramIngestor(cfg)
    raw_items, channels_processed = asyncio.run(ing.fetch_new(channels_override=channels_override))

    # dedup
    dedup_path = os.path.join(state_dir, "dedup.json")
    dedup = DedupStore(dedup_path)
    dedup_data = _dedup_load(dedup, dedup_path)

    new_newsitems: List[object] = []
    for it in raw_items:
        item_id = _newsitem_item_id(it)
        if not item_id:
            continue
        if item_id not in dedup_data:
            new_newsitems.append(it)
            dedup_data[item_id] = 1

    _dedup_save(dedup, dedup_path, dedup_data)

    # normalize to dicts
    items: List[Dict[str, object]] = [_newsitem_to_mapping(it) for it in new_newsitems]

    # filter
    res = filter_items(items, keywords)
    filtered, match_map = _unwrap_filter_result(res)

    # ensure matched_keyword if match_map style is used
    for it in filtered:
        item_id = str(it.get("item_id", "") or "")
        if item_id and not it.get("matched_keyword") and item_id in match_map:
            it["matched_keyword"] = match_map[item_id]

    # writer + style
    style_dir = resolve_style_dir(None)
    out_rows: List[Dict[str, object]] = []

    for item in filtered:
        mk = str(item.get("matched_keyword", "") or "")
        topic = kw_to_topic.get(mk, "")
        style_name = kw_to_style.get(mk, "") or str(item.get("style_name", "") or "")

        examples = styles_dict.get(style_name) or load_style_examples(style_dir, style_name, max_examples=5)

        raw = str(item.get("content", "") or "")
        link = str(item.get("link", "") or "")

        draft = write_draft(
            raw=raw,
            style_name=style_name,
            style_examples=examples,
            topic_or_keyword=topic or mk,
            link=link,
        )

        item["title"] = draft.title
        item["summary_bullets"] = draft.summary_facts.splitlines() if draft.summary_facts else []
        item["styled_draft"] = draft.draft
        item["status"] = "DRAFT"

        out_rows.append(item)

    # append to sheets
    client = SheetsClient(sheet_id=sheet_id, tab_name=tab)
    append_items(out_rows, client=client)

    print(
        f"channels_processed={channels_processed} "
        f"fetched={len(raw_items)} "
        f"new_items={len(new_newsitems)} "
        f"appended={len(out_rows)} "
        f"keywords={len(keywords)} "
        f"admin={admin_enabled}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        raise
