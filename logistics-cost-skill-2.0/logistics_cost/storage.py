"""CSV、JSON和反馈图片的轻量存储函数。"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any, Iterable


def ensure_csv(path: Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        write_csv(path, [], fields)
        return
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        existing_fields = reader.fieldnames or []
    if existing_fields != fields:
        write_csv(path, rows, fields)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path: Path, row: dict[str, Any], fields: list[str]) -> None:
    ensure_csv(path, fields)
    with path.open("a", encoding="utf-8-sig", newline="") as file:
        csv.DictWriter(file, fieldnames=fields, extrasaction="ignore").writerow(row)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temporary.replace(path)


def archive_local_image(source: str, target_dir: Path, target_stem: str) -> str:
    path = Path(source).expanduser()
    if not path.is_file():
        return ""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{target_stem}{path.suffix.lower() or '.img'}"
    shutil.copy2(path, target)
    return target.as_posix()
