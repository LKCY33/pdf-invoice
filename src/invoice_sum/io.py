from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import ResultRecord


def append_jsonl(path: Path, rec: ResultRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(rec.model_dump_json())
        f.write("\n")


def load_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                items.append(json.loads(s))
            except json.JSONDecodeError:
                continue
    return items
