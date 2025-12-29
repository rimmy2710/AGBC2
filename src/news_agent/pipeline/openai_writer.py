from __future__ import annotations

import os
from typing import List, Dict


def _env_bool(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default).strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _truncate(s: str, max_len: int = 1200) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def rewrite_with_openai(
    *,
    topic_or_keyword: str,
    source_link: str,
    raw_text: str,
    style_name: str,
    style_examples: List[str],
    model: str = "gpt-4o-mini",
) -> Dict[str, str]:
    """
    Returns dict with keys: title, summary_facts, draft.

    Safety:
    - If OPENAI_ENABLED=0 or no OPENAI_API_KEY -> raises RuntimeError for caller fallback.
    - Do not pass unsupported params (some models only allow default temperature).
    """
    if not _env_bool("OPENAI_ENABLED", "0"):
        raise RuntimeError("OPENAI_DISABLED")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY_MISSING")

    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError(f"OPENAI_SDK_MISSING: {e}") from e

    client = OpenAI(api_key=api_key)

    examples_block = ""
    if style_examples:
        ex = "\n".join([f"- {x.strip()}" for x in style_examples if x.strip()])
        if ex.strip():
            examples_block = f"\nStyle examples:\n{ex}\n"

    prompt = f"""
You are a news writing assistant.
Goal: rewrite a Telegram news item into a short draft that matches the requested style.

Rules:
- Output MUST be valid JSON with keys: "title", "summary_facts", "draft".
- "summary_facts" must be a bullet list string using "- " prefix (2-5 bullets).
- No hallucinations: only use facts from input text.
- Keep links as provided (do not invent).
- Language: Vietnamese.
- Style name: {style_name}.
{examples_block}

Context:
- Topic/Keyword: {topic_or_keyword}
- Source link: {source_link}

Input text (Telegram message):
\"\"\"{_truncate(raw_text, 2000)}\"\"\"
""".strip()

    # IMPORTANT:
    # Do NOT send temperature here.
    # Some models only support default temperature, and passing any value can 400.
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a careful assistant that outputs strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = resp.choices[0].message.content or "{}"

    import json

    try:
        data = json.loads(content)
    except Exception as e:
        raise RuntimeError(f"OPENAI_BAD_JSON: {e}") from e

    title = (data.get("title") or "").strip()
    summary_facts = (data.get("summary_facts") or "").strip()
    draft = (data.get("draft") or "").strip()

    if not title or not draft:
        raise RuntimeError("OPENAI_EMPTY_FIELDS")

    return {"title": title, "summary_facts": summary_facts, "draft": draft}
