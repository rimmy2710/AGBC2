"""Keyword and topic filtering utilities for news items."""
from __future__ import annotations

import os
from typing import Iterable, List, Mapping, MutableMapping, Sequence


def load_keywords(file_path: str) -> List[str]:
    """Load keywords/topics from a newline-delimited file.

    Empty lines and comments (starting with ``#``) are ignored. Keywords are
    normalized to lowercase for matching.
    """
    if not file_path:
        return []

    if not os.path.exists(file_path):
        return []

    keywords: List[str] = []
    with open(file_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            keywords.append(line.lower())
    return keywords


def _text_from_item(item: Mapping[str, str]) -> str:
    """Extract concatenated text fields from an item for matching.

    This helper pulls from common keys like ``text``, ``message`` or ``content``
    and falls back to an empty string when missing to avoid KeyErrors.
    """
    text_parts: List[str] = []
    for key in ("text", "message", "content", "title"):
        value = item.get(key, "")
        if isinstance(value, str):
            text_parts.append(value)
    return " \n".join(text_parts)


def _match_keyword(text: str, keywords: Sequence[str]) -> str | None:
    lowered = text.lower()
    for keyword in keywords:
        if keyword in lowered:
            return keyword
    return None


def filter_items(
    items: Iterable[Mapping[str, str]], keywords: Sequence[str]
) -> List[MutableMapping[str, str]]:
    """Filter items by keyword/topic and tag them with the matched keyword.

    Args:
        items: Iterable of message dictionaries with ``text``/``content``/``title`` fields.
        keywords: Sequence of lowercase keywords/topics.

    Returns:
        A list of items (shallow-copied) that matched at least one keyword. Each
        returned item includes an extra ``matched_keyword`` key describing the
        match used for downstream logging and sheet output.
    """
    qualified: List[MutableMapping[str, str]] = []
    if not keywords:
        return qualified

    for item in items:
        text = _text_from_item(item)
        matched = _match_keyword(text, keywords)
        if matched:
            clone: MutableMapping[str, str] = dict(item)
            clone["matched_keyword"] = matched
            qualified.append(clone)
    return qualified


def load_and_filter(items: Iterable[Mapping[str, str]]) -> List[MutableMapping[str, str]]:
    """Helper that loads keywords from KEYWORDS_FILE and applies filtering."""
    keywords_file = os.environ.get("KEYWORDS_FILE")
    keywords = load_keywords(keywords_file) if keywords_file else []
    return filter_items(items, keywords)
