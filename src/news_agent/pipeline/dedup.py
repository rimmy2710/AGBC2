from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable


@dataclass
class DedupStore:
    path: str
    max_items: int = 50_000

    def _ensure_parent(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def load(self) -> Dict[str, float]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): float(v) for k, v in data.items()}
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        return {}

    def save(self, data: Dict[str, float]) -> None:
        self._ensure_parent()
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def filter_new(self, item_ids: Iterable[str]) -> Dict[str, bool]:
        now = time.time()
        data = self.load()
        out: Dict[str, bool] = {}
        changed = False

        for item_id in item_ids:
            if item_id in data:
                out[item_id] = False
            else:
                out[item_id] = True
                data[item_id] = now
                changed = True

        if changed and len(data) > self.max_items:
            items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)
            data = dict(items[: self.max_items])
            changed = True

        if changed:
            self.save(data)

        return out
