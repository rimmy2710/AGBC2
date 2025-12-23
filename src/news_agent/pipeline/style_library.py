"""Utility functions to load style samples for AI prompting."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

DEFAULT_STYLE_NAME = "default"


class StyleLibraryError(Exception):
    """Raised when a style library cannot be loaded."""


def _load_text_file(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle.readlines() if line.strip()]
    return lines


def _load_json_file(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    if isinstance(data, dict) and "examples" in data:
        examples = data.get("examples", [])
        return [str(item).strip() for item in examples if str(item).strip()]
    raise StyleLibraryError(f"Unsupported JSON structure in {path}")


def load_style_samples(style_name: str | None = None, base_dir: str | None = None) -> List[str]:
    """Load style examples from STATE_DIR-backed storage.

    The loader supports ``.txt`` and ``.json`` formats. Text files are treated as
    newline-delimited examples, while JSON files can either be a list of strings
    or a dict with an ``examples`` array.
    """
    resolved_style_name = style_name or os.environ.get("STYLE_NAME") or DEFAULT_STYLE_NAME
    resolved_base_dir = base_dir or os.environ.get("STYLE_LIBRARY_DIR")
    if not resolved_base_dir:
        state_dir = os.environ.get("STATE_DIR", "storage")
        resolved_base_dir = os.path.join(state_dir, "style_library")

    base_path = Path(resolved_base_dir)
    if not base_path.exists():
        return []

    for extension, loader in ((".txt", _load_text_file), (".json", _load_json_file)):
        candidate = base_path / f"{resolved_style_name}{extension}"
        if candidate.exists():
            try:
                return loader(candidate)
            except Exception as exc:  # pylint: disable=broad-except
                raise StyleLibraryError(f"Failed to load style library: {candidate}") from exc
    return []
