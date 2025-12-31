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
    v = os.getenv(name, default)
    v = (v or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name, str(default))
    try:
        return int((v or "").strip() or str(default))
    except Exception:
        return default


def _safe_lines(raw: str) -> List[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
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
    Rules:
    - Only call OpenAI if:
        OPENAI_ENABLED=1 AND OPENAI_API_KEY set AND MAX_AI_ITEMS > 0
      (MAX_AI_ITEMS=0 is a hard-disable guard for cron stability)
    - If OpenAI fails for any reason, fallback (pipeline must not break).
    """
    openai_enabled = _env_bool("OPENAI_ENABLED", "0")
    api_key_present = bool(os.getenv("OPENAI_API_KEY", "").strip())
    max_ai_items = _env_int("MAX_AI_ITEMS", 1)

    if openai_enabled and api_key_present and max_ai_items > 0:
        try:
            from news_agent.pipeline.openai_writer import rewrite_with_openai

            # Keep default consistent with openai_writer
            model = (os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini")
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
            # keep logs short, never crash pipeline
            msg = f"{type(e).__name__}: {e}"
            msg = msg.strip()
            if len(msg) > 220:
                msg = msg[:220] + "..."
            print(f"[openai_writer] fallback due to error: {msg}", flush=True)

    return _fallback_write_draft(
        raw=raw,
        style_name=style_name,
        style_examples=style_examples,
        topic_or_keyword=topic_or_keyword,
        link=link,
    )
