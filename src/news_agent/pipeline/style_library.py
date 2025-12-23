from __future__ import annotations

import os
from typing import List

DEFAULT_STATE_DIR = "storage"
DEFAULT_STYLE_DIRNAME = "style_library"
DEFAULT_MAX_EXAMPLES = 10


def resolve_style_dir(explicit_dir: str | None = None) -> str:
    if explicit_dir:
        return explicit_dir
    env_dir = os.environ.get("STYLE_LIBRARY_DIR")
    if env_dir:
        return env_dir
    state_dir = os.environ.get("STATE_DIR", DEFAULT_STATE_DIR)
    return os.path.join(state_dir, DEFAULT_STYLE_DIRNAME)


def load_style_examples(style_dir: str, style_name: str, max_examples: int = DEFAULT_MAX_EXAMPLES) -> List[str]:
    """Load style examples from <style_dir>/<style_name>.txt.

    Format: examples separated by a line containing only '---' (optional).
    If no separator, treat whole file as a single example.
    """
    if not style_name:
        return []

    path = os.path.join(style_dir, f"{style_name}.txt")
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    if not raw:
        return []

    parts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
    if not parts:
        parts = [raw]

    return parts[: max(1, int(max_examples))]
