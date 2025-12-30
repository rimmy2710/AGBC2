from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


@dataclass
class Draft:
    title: str
    summary_facts: str
    draft: str


def _env_bool(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default).strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _safe_lines(raw: str) -> List[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    # Keep non-empty lines, trim
    return [ln.strip() for ln in raw.splitlines() if ln.strip()]


def _fallback_write_draft(
    *,
    raw: str,
    style_name: str,
    style_examples: List[str],
    topic_or_keyword: str,
    link: str,
) -> Draft:
    """
    Cheap fallback writer (no OpenAI).
    Keeps pipeline working even when OpenAI is disabled or unavailable.
    """
    lines = _safe_lines(raw)
    first = lines[0] if lines else ""
    second = lines[1] if len(lines) > 1 else ""

    title = first[:120] if first else (f"Update: {topic_or_keyword}" if topic_or_keyword else "Telegram update")
    bullets: List[str] = []
    if first:
        bullets.append(f"- {first}")
    if second:
        bullets.append(f"- {second}")
    summary_facts = "\n".join(bullets)

    # Very simple “styled” draft
    draft_lines: List[str] = []
    draft_lines.append(f"[STYLE: {style_name}]")
    if topic_or_keyword:
        draft_lines.append(f"Topic: {topic_or_keyword}")
    if link:
        draft_lines.append(f"Source: {link}")
    if summary_facts:
        draft_lines.append("Summary:")
        draft_lines.extend(summary_facts.splitlines())
    draft_lines.append("Draft:")
    draft_lines.extend(lines if lines else ([raw.strip()] if raw else []))

    return Draft(title=title, summary_facts=summary_facts, draft="\n".join(draft_lines).strip())


def write_draft(
    *,
    raw: str,
    style_name: str,
    style_examples: List[str],
    topic_or_keyword: str,
    link: str,
) -> Draft:
    """
    Main entry used by runner.
    - If OPENAI_ENABLED=1 and OPENAI_API_KEY is set, try OpenAI rewrite.
    - Otherwise fallback writer.
    - If OpenAI fails for any reason, fallback (pipeline must not break).
    """
    if _env_bool("OPENAI_ENABLED", "0") and os.getenv("OPENAI_API_KEY", "").strip():
        try:
            from news_agent.pipeline.openai_writer import rewrite_with_openai

            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
            out = rewrite_with_openai(
                topic_or_keyword=topic_or_keyword,
                source_link=link,
                raw_text=raw,
                style_name=style_name,
                style_examples=style_examples,
                model=model,
            )
            return Draft(
                title=(out.get("title") or "").strip(),
                summary_facts=(out.get("summary_facts") or "").strip(),
                draft=(out.get("draft") or "").strip(),
            )
        except Exception as e:
            err = str(e)
            if len(err) > 200:
                err = err[:200] + "..."
            print(f"[openai_writer] fallback due to error: {err}", flush=True)

    return _fallback_write_draft(
        raw=raw,
        style_name=style_name,
        style_examples=style_examples,
        topic_or_keyword=topic_or_keyword,
        link=link,
    )
