from __future__ import annotations

import os
from news_agent.pipeline.ai_writer import write_draft
from news_agent.pipeline.style_library import load_style_examples, resolve_style_dir


def main() -> None:
    style_name = os.getenv("STYLE_NAME", "telegram_casual")
    style_dir = resolve_style_dir(None)
    examples = load_style_examples(style_dir, style_name, max_examples=5)

    raw = "BTC ETF approved. Market reacts with higher volume.\nSecond line context."
    out = write_draft(
        raw=raw,
        style_name=style_name,
        style_examples=examples,
        topic_or_keyword="btc",
        link="https://t.me/x/1",
    )
    print("title=", out.title)
    print("summary_facts=\n", out.summary_facts)
    print("draft_preview=\n", out.draft[:320])


if __name__ == "__main__":
    main()
