from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import gspread


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _load_json(path: str) -> Dict[str, int]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()}
        return {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _save_json_atomic(path: str, data: Dict[str, int]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _safe_str(v: object) -> str:
    return ("" if v is None else str(v)).strip()


def _norm_header(h: str) -> str:
    return _safe_str(h).lower().replace(" ", "_")


def _open_ws(sh, title: str):
    try:
        return sh.worksheet(title)
    except Exception:
        return sh.add_worksheet(title=title, rows=1000, cols=30)


def _col_index(header: List[str]) -> Dict[str, int]:
    m: Dict[str, int] = {}
    for i, h in enumerate(header):
        key = _norm_header(h)
        if key:
            m[key] = i
    return m


def _pick_idx(idx: Dict[str, int], *candidates: str) -> int:
    for c in candidates:
        k = _norm_header(c)
        if k in idx:
            return idx[k]
    return -1


def _fallback_key(time_iso: str, source: str, title: str, link: str) -> str:
    if link:
        return f"link:{link}"
    raw = f"{time_iso}|{source}|{title}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"hash:{h}"


def _find_header_row(ws, scan_rows: int = 25) -> Tuple[int, List[str]]:
    """
    Find the most likely header row within first N rows.
    Returns (header_row_index_1based, header_values)
    """
    candidates: List[Tuple[int, int, List[str]]] = []
    keys = ["time", "source", "title", "draft", "link", "status", "topic", "keyword"]
    for r in range(1, scan_rows + 1):
        row = ws.row_values(r)
        norm = [(c or "").strip().lower() for c in row]
        non_empty = sum(1 for x in norm if x)
        if non_empty < 3:
            continue
        score = 0
        for k in keys:
            if any(k in x for x in norm):
                score += 1
        if score >= 2:
            candidates.append((score, r, row))

    if not candidates:
        # fallback to row 1
        return 1, ws.row_values(1)

    candidates.sort(reverse=True)
    score, r, row = candidates[0]
    return r, row


def _read_table_with_header_detect(ws, scan_rows: int = 25, max_rows: int | None = None) -> Tuple[List[str], List[List[str]]]:
    header_row, header = _find_header_row(ws, scan_rows=scan_rows)
    if not header:
        return [], []

    # fetch all values once (gspread fastest this way)
    values = ws.get_all_values()
    if not values:
        return [], []

    # rows start after header_row
    rows = values[header_row:]
    if max_rows is not None and len(rows) > max_rows:
        rows = rows[-max_rows:]

    width = len(header)
    norm_rows: List[List[str]] = []
    for r in rows:
        if len(r) < width:
            r = r + [""] * (width - len(r))
        elif len(r) > width:
            r = r[:width]
        norm_rows.append(r)

    return header, norm_rows


@dataclass
class LearningConfig:
    sheet_id: str
    source_tab: str = "AGBC2 – News Draft"
    dest_tab: str = "learning_suggestions"
    status_filter: str = "APPROVED"
    min_draft_chars: int = 80
    max_rows_scan: int = 2000
    state_dir: str = "storage"
    dedup_file: str = "learning_dedup.json"
    header_scan_rows: int = 25


@dataclass
class LearningSuggestion:
    key: str
    time_iso: str
    topic_or_keyword: str
    style_name: str
    title: str
    draft: str
    link: str
    status: str = "SUGGESTED"


def generate_suggestions(cfg: LearningConfig) -> Tuple[int, int, int]:
    """
    Returns (scanned_rows, eligible_rows, appended_rows)
    """
    _ensure_dir(cfg.state_dir)
    dedup_path = os.path.join(cfg.state_dir, cfg.dedup_file)
    dedup = _load_json(dedup_path)

    gc = gspread.service_account()
    sh = gc.open_by_key(cfg.sheet_id)

    src = _open_ws(sh, cfg.source_tab)
    header, rows = _read_table_with_header_detect(
        src,
        scan_rows=cfg.header_scan_rows,
        max_rows=cfg.max_rows_scan,
    )
    if not header:
        return 0, 0, 0

    idx = _col_index(header)

    # common column variants
    i_time = _pick_idx(idx, "Time", "time")
    i_source = _pick_idx(idx, "Source", "source")
    i_topic = _pick_idx(idx, "Topic/Keyword", "Topic", "Keyword", "topic/keyword", "topic_keyword")
    i_title = _pick_idx(idx, "Title", "title")
    i_draft = _pick_idx(idx, "Draft (styled)", "Draft", "draft", "styled_draft", "draft_styled")
    i_link = _pick_idx(idx, "Link", "link")
    i_status = _pick_idx(idx, "Status", "status")
    i_style = _pick_idx(idx, "style_name", "Style", "style")

    # item_id may not exist
    i_item = _pick_idx(idx, "item_id", "Item ID", "item id", "itemId", "ItemID")

    scanned = len(rows)

    eligible: List[LearningSuggestion] = []
    status_target = (cfg.status_filter or "").strip().upper()

    for r in rows:
        time_iso = _safe_str(r[i_time]) if i_time >= 0 else ""
        source = _safe_str(r[i_source]) if i_source >= 0 else ""
        topic = _safe_str(r[i_topic]) if i_topic >= 0 else ""
        title = _safe_str(r[i_title]) if i_title >= 0 else ""
        link = _safe_str(r[i_link]) if i_link >= 0 else ""
        status = _safe_str(r[i_status]) if i_status >= 0 else ""
        draft = _safe_str(r[i_draft]) if i_draft >= 0 else ""
        style_name = _safe_str(r[i_style]) if i_style >= 0 else ""

        if status_target:
            if status.strip().upper() != status_target:
                continue

        if len(draft) < cfg.min_draft_chars:
            continue

        item_id = _safe_str(r[i_item]) if i_item >= 0 else ""
        key = item_id or _fallback_key(time_iso=time_iso, source=source, title=title, link=link)
        if key in dedup:
            continue

        eligible.append(
            LearningSuggestion(
                key=key,
                time_iso=time_iso,
                topic_or_keyword=topic,
                style_name=style_name,
                title=title,
                draft=draft,
                link=link,
            )
        )

    eligible_count = len(eligible)
    if not eligible:
        return scanned, eligible_count, 0

    dest = _open_ws(sh, cfg.dest_tab)

    dest_values = dest.get_all_values()
    if not dest_values:
        dest.append_row(
            [
                "Time",
                "learn_key",
                "Topic/Keyword",
                "style_name",
                "Title",
                "Draft (styled)",
                "Link",
                "Status",
            ]
        )

    appended = 0
    for s in eligible:
        dest.append_row(
            [
                s.time_iso,
                s.key,
                s.topic_or_keyword,
                s.style_name,
                s.title,
                s.draft,
                s.link,
                s.status,
            ]
        )
        dedup[s.key] = 1
        appended += 1

    _save_json_atomic(dedup_path, dedup)
    return scanned, eligible_count, appended
