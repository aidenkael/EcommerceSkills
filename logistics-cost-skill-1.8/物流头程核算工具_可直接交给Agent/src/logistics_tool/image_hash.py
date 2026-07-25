from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash_file(path: Path, size: int = 8) -> str | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as img:
            img = img.convert("L").resize((size + 1, size))
            pixels = list(img.getdata())
    except Exception:
        return None
    bits: list[bool] = []
    for y in range(size):
        row = pixels[y * (size + 1):(y + 1) * (size + 1)]
        bits.extend(row[x] > row[x + 1] for x in range(size))
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:0{size * size // 4}x}"


def hamming_hex(a: str | None, b: str | None) -> int | None:
    if not a or not b or len(a) != len(b):
        return None
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except ValueError:
        return None
