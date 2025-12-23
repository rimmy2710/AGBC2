"""Smoke test for keyword filtering."""
from __future__ import annotations

from src.news_agent.pipeline import filter as keyword_filter


def main() -> None:
    keywords = keyword_filter.load_keywords("storage/keywords.txt")
    sample_text = "BTC surges past 70k as ETF inflows rise"
    matched = keyword_filter.match_keyword(sample_text, keywords)
    qualified, match_map = keyword_filter.filter_items(
        [
            {"item_id": "sample-1", "text": sample_text},
        ],
        keywords,
    )

    print("Loaded keywords:", keywords)
    print("Matched keyword:", matched)
    print("Qualified items:", qualified)
    print("Match map:", match_map)


if __name__ == "__main__":
    main()
