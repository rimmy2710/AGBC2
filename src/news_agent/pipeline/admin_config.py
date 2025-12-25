from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import gspread
except ImportError:  # pragma: no cover
    gspread = None  # type: ignore


TRUE_SET = {"true", "1", "yes", "y", "on"}
FALSE_SET = {"false", "0", "no", "n", "off"}


def _must_gspread() -> None:
    if gspread is None:
        raise RuntimeError("gspread is not installed; cannot load admin config")


def _normalize_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False
    return default


def _normalize_channel(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    m = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", s)
    if m:
        return f"@{m.group(1)}"
    if not s.startswith("@"):
        return f"@{s}"
    return s


def _service_account_client():
    _must_gspread()
    creds_file = (
        os.environ.get("GSPREAD_SERVICE_ACCOUNT_FILE")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()
    if creds_file:
        if not os.path.exists(creds_file):
            raise FileNotFoundError(f"Service account file not found: {creds_file}")
        return gspread.service_account(filename=creds_file)
    return gspread.service_account()  # fallback ~/.config/gspread/service_account.json


def _open_worksheet(sheet_id: str, tab_name: str):
    client = _service_account_client()
    ss = client.open_by_key(sheet_id)
    return ss.worksheet(tab_name)


def _records(sheet_id: str, tab_name: str) -> List[dict]:
    ws = _open_worksheet(sheet_id, tab_name)
    return ws.get_all_records(default_blank="")


@dataclass(frozen=True)
class KeywordRule:
    keyword: str
    topic: str
    enabled: bool = True
    style_name: str = ""


@dataclass(frozen=True)
class AdminConfig:
    channels: List[str]
    keyword_rules: List[KeywordRule]
    styles: Dict[str, List[str]]


def load_channels(sheet_id: str, tab_name: str = "channels") -> List[str]:
    rows = _records(sheet_id, tab_name)
    out: List[str] = []
    for r in rows:
        ch = _normalize_channel(str(r.get("channel", "")).strip())
        if not ch:
            continue
        if not _normalize_bool(r.get("enabled", True), default=True):
            continue
        out.append(ch)

    seen = set()
    deduped: List[str] = []
    for ch in out:
        if ch in seen:
            continue
        seen.add(ch)
        deduped.append(ch)
    return deduped


def load_keyword_rules(sheet_id: str, tab_name: str = "keywords") -> List[KeywordRule]:
    rows = _records(sheet_id, tab_name)
    rules: List[KeywordRule] = []
    for r in rows:
        kw = str(r.get("keyword", "")).strip().lower()
        if not kw:
            continue
        enabled = _normalize_bool(r.get("enabled", True), default=True)
        if not enabled:
            continue
        topic = str(r.get("topic", "")).strip() or kw
        style_name = str(r.get("style_name", "")).strip()
        rules.append(KeywordRule(keyword=kw, topic=topic, enabled=True, style_name=style_name))
    return rules


def load_styles(sheet_id: str, tab_name: str = "styles", max_examples: int = 10) -> Dict[str, List[str]]:
    rows = _records(sheet_id, tab_name)
    styles: Dict[str, List[str]] = {}
    for r in rows:
        name = str(r.get("style_name", "")).strip()
        if not name:
            continue
        raw = str(r.get("example", "")).strip()
        if not raw:
            styles[name] = []
            continue
        parts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
        if not parts:
            parts = [raw]
        styles[name] = parts[: max(1, int(max_examples))]
    return styles


def load_admin_config(
    sheet_id: Optional[str] = None,
    channels_tab: str = "channels",
    keywords_tab: str = "keywords",
    styles_tab: str = "styles",
    max_style_examples: int = 10,
) -> AdminConfig:
    sid = (sheet_id or os.environ.get("ADMIN_CONFIG_SHEET_ID") or "").strip()
    if not sid:
        raise RuntimeError("ADMIN_CONFIG_SHEET_ID is not set")
    channels = load_channels(sid, channels_tab)
    keyword_rules = load_keyword_rules(sid, keywords_tab)
    styles = load_styles(sid, styles_tab, max_examples=max_style_examples)
    return AdminConfig(channels=channels, keyword_rules=keyword_rules, styles=styles)


def build_keyword_maps(rules: List[KeywordRule]) -> Tuple[List[str], dict, dict]:
    keywords: List[str] = []
    kw_to_topic: Dict[str, str] = {}
    kw_to_style: Dict[str, str] = {}
    for r in rules:
        keywords.append(r.keyword)
        kw_to_topic[r.keyword] = r.topic
        if r.style_name:
            kw_to_style[r.keyword] = r.style_name
    return keywords, kw_to_topic, kw_to_style
