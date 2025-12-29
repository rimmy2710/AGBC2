from __future__ import annotations

import os
import sys

from news_agent.pipeline.self_learning import LearningConfig, generate_suggestions


def _must_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def main() -> int:
    sheet_id = _must_env("GOOGLE_SHEET_ID")

    cfg = LearningConfig(
        sheet_id=sheet_id,
        source_tab=os.getenv("GOOGLE_SHEET_TAB", "AGBC2 – News Draft"),
        dest_tab=os.getenv("LEARNING_SHEET_TAB", "learning_suggestions"),
        status_filter=os.getenv("LEARNING_STATUS_FILTER", "APPROVED"),
        min_draft_chars=int(os.getenv("LEARNING_MIN_DRAFT_CHARS", "80")),
        max_rows_scan=int(os.getenv("LEARNING_MAX_SCAN", "2000")),
        state_dir=os.getenv("STATE_DIR", "storage"),
    )

    scanned, eligible, appended = generate_suggestions(cfg)
    print(
        f"self_learning scanned={scanned} eligible={eligible} appended={appended} "
        f"status_filter={cfg.status_filter} dest_tab={cfg.dest_tab}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        raise
