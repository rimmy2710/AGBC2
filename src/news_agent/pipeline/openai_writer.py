from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if v is not None else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)) or str(default))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)) or str(default))
    except Exception:
        return default


def _style_block(style_name: str, style_examples: List[str]) -> str:
    ex_lines: List[str] = []
    for i, ex in enumerate(style_examples or [], start=1):
        ex = (ex or "").strip()
        if not ex:
            continue
        ex_lines.append(f"Example {i}:\n{ex}")
        if i >= 3:
            break

    examples_txt = "\n\n".join(ex_lines) if ex_lines else "(no examples provided)"
    return f"""STYLE NAME: {style_name}

STYLE EXAMPLES (follow tone/format, do not copy verbatim):
{examples_txt}
"""


def _build_messages(
    *,
    topic_or_keyword: str,
    source_link: str,
    raw_text: str,
    style_name: str,
    style_examples: List[str],
) -> List[Dict[str, str]]:
    style_txt = _style_block(style_name=style_name, style_examples=style_examples)

    system = (
        "You are a crypto news editor. Rewrite Telegram-sourced raw text into a clean draft.\n"
        "Return STRICT JSON only (no markdown), matching the schema:\n"
        '{ "title": string, "summary_facts": string, "draft": string }\n'
        "- title: 1 line.\n"
        "- summary_facts: 2-4 bullet lines, each starting with '- '. Facts only.\n"
        "- draft: short, readable, aligned to style examples.\n"
        "Safety: do not invent facts; if info is missing, keep it vague rather than guessing."
    )

    user = f"""TOPIC_OR_KEYWORD: {topic_or_keyword}
SOURCE_LINK: {source_link}

{style_txt}

RAW_TEXT:
{raw_text}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_json_strict(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    if not t:
        raise ValueError("Empty response")

    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in response")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("JSON is not an object")
    return obj


def _ensure_fields(obj: Dict[str, Any]) -> Dict[str, str]:
    title = str(obj.get("title") or "").strip()
    summary_facts = str(obj.get("summary_facts") or "").strip()
    draft = str(obj.get("draft") or "").strip()

    if summary_facts and not summary_facts.lstrip().startswith("-"):
        lines = [ln.strip() for ln in summary_facts.splitlines() if ln.strip()]
        summary_facts = "\n".join([ln if ln.startswith("-") else f"- {ln}" for ln in lines])

    return {"title": title, "summary_facts": summary_facts, "draft": draft}


def _client():
    """
    FAIL-FAST client: by default no retries and short timeout.
    This prevents 429 from blocking cron for long due to auto-retry.
    """
    from openai import OpenAI

    max_retries = _env_int("OPENAI_MAX_RETRIES", 0)
    timeout = _env_float("OPENAI_TIMEOUT", 15.0)

    return OpenAI(
        api_key=_env("OPENAI_API_KEY"),
        max_retries=max_retries,
        timeout=timeout,
    )


def _is_unsupported_param_error(e: Exception, param_name: str) -> bool:
    msg = f"{e}"
    return ("Unsupported parameter" in msg) and (f"'{param_name}'" in msg or f'"{param_name}"' in msg)


def rewrite_with_openai(
    *,
    topic_or_keyword: str,
    source_link: str,
    raw_text: str,
    style_name: str,
    style_examples: List[str],
    model: Optional[str] = None,
) -> Dict[str, str]:
    """
    Returns: {"title":..., "summary_facts":..., "draft":...}
    Raises exceptions on failure so caller can fallback.
    """
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    model_name = (model or _env("OPENAI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"

    messages = _build_messages(
        topic_or_keyword=(topic_or_keyword or "").strip(),
        source_link=(source_link or "").strip(),
        raw_text=(raw_text or "").strip(),
        style_name=(style_name or "").strip() or "default",
        style_examples=style_examples or [],
    )

    max_out = _env_int("OPENAI_MAX_TOKENS", 450)
    temperature = _env_float("OPENAI_TEMPERATURE", 0.4)

    c = _client()

    base_kwargs: Dict[str, Any] = dict(
        model=model_name,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    # Prefer max_completion_tokens first (newer models), fallback to max_tokens if needed.
    try_orders = [
        ("max_completion_tokens", max_out),
        ("max_tokens", max_out),
    ]

    last_err: Optional[Exception] = None
    for token_param, token_value in try_orders:
        kwargs = dict(base_kwargs)
        kwargs[token_param] = token_value
        try:
            resp = c.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content or ""
            obj = _parse_json_strict(text)
            out = _ensure_fields(obj)
            if not out["title"] and not out["draft"]:
                raise ValueError("Model returned empty output")
            return out
        except Exception as e:
            last_err = e
            # Only fallback to the other token param when it's clearly unsupported-parameter
            if _is_unsupported_param_error(e, token_param):
                continue
            raise

    assert last_err is not None
    raise last_err


if __name__ == "__main__":
    out = rewrite_with_openai(
        topic_or_keyword="btc",
        source_link="https://t.me/example/1",
        raw_text="BTC ETF approved. Market reacts with higher volume.\nSecond line context.",
        style_name="telegram_casual",
        style_examples=["Tóm tắt kiểu trader..."],
        model=_env("OPENAI_MODEL", "gpt-4o-mini"),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
