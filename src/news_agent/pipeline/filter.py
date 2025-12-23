cat > src/news_agent/pipeline/filter.py << 'EOF'
"""Keyword/topic filtering utilities."""
from __future__ import annotations

import os
from typing import Iterable, List, Mapping, MutableMapping, Sequence, Tuple

DEFAULT_STATE_DIR = "storage"
DEFAULT_KEYWORDS_FILENAME = "keywords.txt"


def _resolve_keywords_path(explicit_path: str | None = None) -> str:
    """Resolve the keywords file path from env or defaults."""
    if explicit_path:
        return explicit_path
    env_path = os.environ.get("KEYWORDS_FILE")
    if env_path:
        return env_path
    state_dir = os.environ.get("STATE_DIR", DEFAULT_STATE_DIR)
    return os.path.join(state_dir, DEFAULT_KEYWORDS_FILENAME)


def load_keywords(path: str | None = None) -> List[str]:
    """Load keywords/topics from a newline-delimited file.

    Empty lines and comment lines beginning with '#' are ignored.
    Keywords are normalized to lowercase for case-insensitive matching.
    """
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
    """Return the first matched keyword (case-insensitive) or None."""
    if not text:
        return None
    lowered_text = text.lower()
    for keyword in keywords:
        if keyword in lowered_text:
            return keyword
    return None


def _text_from_item(item: Mapping[str, str]) -> str:
    """Extract concatenated text fields from an item for matching."""
    text_parts: List[str] = []
    for key in ("text", "message", "content", "title"):
        value = item.get(key, "")
        if isinstance(value, str) and value:
            text_parts.append(value)
    return "\n".join(text_parts)


def filter_items(
    items: Iterable[Mapping[str, str]],
    keywords: Sequence[str],
) -> Tuple[List[MutableMapping[str, str]], MutableMapping[str, str]]:
    """Filter items by keyword/topic and map item_ids to matched keyword.

    Returns:
      qualified_items: list of (shallow-copied) items that matched
      match_map: dict[item_id] = matched_keyword
    """
    qualified: List[MutableMapping[str, str]] = []
    match_map: MutableMapping[str, str] = {}

    if not keywords:
        return qualified, match_map

    for item in items:
        text = _text_from_item(item)
        matched = match_keyword(text, keywords)
        if not matched:
            continue

        clone: MutableMapping[str, str] = dict(item)
        qualified.append(clone)

        item_id = str(item.get("item_id", ""))
        if not item_id:
            # fallback stable key for debugging only
            item_id = f"idx:{len(match_map)}"
        match_map[item_id] = matched

    return qualified, match_map
EOF
