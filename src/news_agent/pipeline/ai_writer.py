from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class DraftOutput:
    title: str
    summary_facts: str
    draft: str


def _make_title(raw: str, fallback: str = "Crypto update") -> str:
    text = (raw or "").strip()
    if not text:
        return fallback
    first = text.splitlines()[0].strip()
    return first if len(first) <= 120 else first[:117] + "..."


def _facts_summary(raw: str, max_bullets: int = 4) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets: List[str] = []
    for ln in lines:
        if len(bullets) >= max_bullets:
            break
        if len(ln) > 240:
            ln = ln[:237] + "..."
        bullets.append(f"- {ln}")
    return "\n".join(bullets)


def _style_prefix(style_name: str, style_examples: List[str]) -> str:
    name = (style_name or "").strip() or "default"
    out = [f"[STYLE: {name}]"]
    if style_examples:
        ex = (style_examples[0] or "").strip()
        if ex:
            excerpt = ex[:300].replace("\n", " ").strip()
            out.append(f"Reference tone excerpt: {excerpt}")
    return "\n".join(out)


def write_draft(
    raw: str,
    style_name: str,
    style_examples: List[str],
    topic_or_keyword: str = "",
    link: str = "",
) -> DraftOutput:
    title = _make_title(raw)
    summary = _facts_summary(raw)

    header: List[str] = []
    if topic_or_keyword.strip():
        header.append(f"Topic: {topic_or_keyword.strip()}")
    if link.strip():
        header.append(f"Source: {link.strip()}")

    style_guide = _style_prefix(style_name, style_examples)

    raw_clean = (raw or "").strip()
    if len(raw_clean) > 1200:
        raw_clean = raw_clean[:1197] + "..."

    draft_lines: List[str] = [style_guide]
    if header:
        draft_lines.append("\n".join(header))
    if summary:
        draft_lines.append("Summary:")
        draft_lines.append(summary)
    draft_lines.append("Draft:")
    draft_lines.append(raw_clean)

    return DraftOutput(title=title, summary_facts=summary, draft="\n".join(draft_lines).strip())
