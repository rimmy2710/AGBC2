"""AI writing helpers for generating titles, summaries and styled drafts."""
from __future__ import annotations

import textwrap
from typing import Dict, List, Mapping


def _select_source_text(item: Mapping[str, str]) -> str:
    for key in ("text", "content", "message", "body"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def generate_title(source_text: str, fallback: str | None = None) -> str:
    if not source_text and fallback:
        return fallback
    if not source_text:
        return ""
    words = source_text.split()
    trimmed = " ".join(words[:12]).rstrip("., ")
    return trimmed


def summarize_facts(source_text: str, max_bullets: int = 3) -> List[str]:
    if not source_text:
        return []
    sentences = [part.strip() for part in source_text.replace("\n", " ").split(".") if part.strip()]
    bullets: List[str] = []
    for sentence in sentences[:max_bullets]:
        bullets.append(sentence)
    return bullets


def _apply_style(source_text: str, style_samples: List[str], style_name: str) -> str:
    if not source_text:
        return ""
    if not style_samples:
        return source_text
    prefix = f"[{style_name}] " if style_name else ""
    sample_hint = " ".join(style_samples[:2])
    draft = textwrap.shorten(source_text, width=400, placeholder="…")
    return f"{prefix}{draft}\n\n# Style guidance:\n{sample_hint}"


def compose_draft(item: Mapping[str, str], style_samples: List[str], style_name: str) -> Dict[str, object]:
    """Produce structured writing outputs from a source item.

    The implementation is provider-agnostic to avoid coupling to any particular
    LLM backend. Prompts should always avoid fabricating numbers or facts; this
    stub keeps transformations minimal to respect that guarantee while remaining
    pluggable for real LLM calls in production.
    """
    source_text = _select_source_text(item)
    fallback_title = item.get("title") if isinstance(item.get("title"), str) else None

    title = generate_title(source_text, fallback=fallback_title)
    summary_bullets = summarize_facts(source_text)
    styled_draft = _apply_style(source_text, style_samples, style_name)

    return {
        "title": title,
        "summary_bullets": summary_bullets,
        "styled_draft": styled_draft,
    }
