from __future__ import annotations

import os
from news_agent.pipeline.admin_config import load_admin_config, build_keyword_maps


def main() -> None:
    sheet_id = os.environ.get("ADMIN_CONFIG_SHEET_ID", "").strip()
    if not sheet_id:
        raise SystemExit("Missing ADMIN_CONFIG_SHEET_ID")

    cfg = load_admin_config(
        sheet_id=sheet_id,
        channels_tab=os.environ.get("ADMIN_CHANNELS_TAB", "channels"),
        keywords_tab=os.environ.get("ADMIN_KEYWORDS_TAB", "keywords"),
        styles_tab=os.environ.get("ADMIN_STYLES_TAB", "styles"),
        max_style_examples=int(os.environ.get("STYLE_MAX_EXAMPLES", "10")),
    )

    keywords, kw_to_topic, kw_to_style = build_keyword_maps(cfg.keyword_rules)

    print("channels_count=", len(cfg.channels))
    print("channels_preview=", cfg.channels[:5])
    print("keywords_count=", len(keywords))
    print("keywords_preview=", keywords[:10])
    print("styles_count=", len(cfg.styles))
    if cfg.styles:
        first = next(iter(cfg.styles.keys()))
        print("first_style=", first, "examples=", len(cfg.styles[first]))
    print("kw_to_topic_preview=", dict(list(kw_to_topic.items())[:5]))
    print("kw_to_style_preview=", dict(list(kw_to_style.items())[:5]))


if __name__ == "__main__":
    main()
