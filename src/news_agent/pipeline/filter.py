"""Keyword/topic filtering utilities."""
from __future__ import annotations

import os
from typing import Iterable, List, Mapping, MutableMapping, Sequence, Tuple

DEFAULT_STATE_DIR = "storage"
DEFAULT_KEYWORDS_FILENAME = "keywords.txt"


def _resolve_keywords_path(explicit_path: str | None = None) -> str:
    if explicit_path:
        return explicit_path
    env_path = os.environ.get("KEYWORDS_FILE")
    if env_path:
        return env_path
    state_dir = os.environ.get("STATE_DIR", DEFAULT_STATE_DIR)
    return os.path.join(state_dir, DEFAULT_KEYWORDS_FILENAME)


def load_keywords(path: str | None = None) -> List[str]:
    resolved_path = _resolve_keywords_path(path)
    if not resolved_path or not os.path.exists(resolved_path):
        return []

    keywords: List[str] = []
    with open(resolved_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            keywords.append(line.lower())
    return keywords


def match_keyword(text: str, keywords: Sequence[str]) -> str | None:
    if not text:
        return None
    lowered_text = text.lower()
    for keyword in keywords:
        if keyword in lowered_text:
            return keyword
    return None


def _text_from_item(item: Mapping[str, str]) -> str:
    parts: List[str] = []
    for key in ("text", "message", "content", "title"):
        v = item.get(key, "")
        if isinstance(v, str) and v:
            parts.append(v)
    return "\n".join(parts)


def filter_items(
    items: Iterable[Mapping[str, str]],
    keywords: Sequence[str],
) -> Tuple[List[MutableMapping[str, str]], MutableMapping[str, str]]:
    qualified: List[MutableMapping[str, str]] = []
    match_map: MutableMapping[str, str] = {}

    if not keywords:
        return qualified, match_map

    for item in items:
        matched = match_keyword(_text_from_item(item), keywords)
        if not matched:
            continue

        qualified.append(dict(item))
        item_id = str(item.get("item_id", "")) or f"idx:{len(match_map)}"
        match_map[item_id] = matched

    return qualified, match_map
