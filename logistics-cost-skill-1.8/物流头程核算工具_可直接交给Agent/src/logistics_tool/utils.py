from __future__ import annotations

import json
import math
import os
import re
import statistics
from pathlib import Path
from typing import Any, Iterable


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} 第 {lineno} 行不是合法 JSON: {exc}") from exc
    return items


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def normalize_text(text: Any) -> str:
    s = str(text or "").lower().strip()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[\s,，;；:：|/\\()（）\[\]【】]+", " ", s)
    return s


def text_tokens(text: Any) -> set[str]:
    s = normalize_text(text)
    tokens: set[str] = set(re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", s))
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", s)
    stop = {"一件", "一套", "一个", "商品", "实际", "尺寸", "重量", "未核实", "供参考", "同款"}
    for chunk in chinese_chunks:
        if chunk not in stop:
            tokens.add(chunk)
        for n in (2, 3):
            if len(chunk) >= n:
                tokens.update(chunk[i:i+n] for i in range(len(chunk) - n + 1))
    return {t for t in tokens if t and t not in stop}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def percentile(values: Iterable[float], p: float) -> float | None:
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def weighted_median(values: list[float], weights: list[float]) -> float | None:
    pairs = sorted((float(v), max(0.0, float(w))) for v, w in zip(values, weights))
    if not pairs:
        return None
    total = sum(w for _, w in pairs)
    if total <= 0:
        return statistics.median(v for v, _ in pairs)
    half = total / 2.0
    running = 0.0
    for value, weight in pairs:
        running += weight
        if running >= half:
            return value
    return pairs[-1][0]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)
