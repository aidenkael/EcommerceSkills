"""文件交付 — 用户明确要求生成文件时创建真实UTF-8文件（原子写入）。"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path


def write_markdown_artifact(content: str, output_path: Path) -> Path:
    """原子写入 MD 文件。

    - 在目标目录创建临时文件
    - UTF-8 写入并 flush/fsync
    - 成功后 os.replace 到目标路径
    - 失败时删除临时文件，原目标文件保持不变

    Returns:
        写入后的绝对路径
    Raises:
        OSError: 写入失败
    """
    p = Path(output_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp", prefix=".artifact_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(p))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return p


def suggest_output_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "output"
