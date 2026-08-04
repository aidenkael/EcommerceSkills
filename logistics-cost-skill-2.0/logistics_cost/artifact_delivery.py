"""文件交付 — 用户明确要求生成MD文件时创建真实UTF-8文件。"""
from __future__ import annotations

import os
import re
from pathlib import Path


def _safe_filename(text: str, max_len: int = 60) -> str:
    """清理文件名：移除非法字符，限制长度。"""
    if not text:
        return "audit"
    # 保留中文、字母、数字、连字符
    clean = re.sub(r"[^\w\u4e00-\u9fff\-\s]", "", text)
    clean = re.sub(r"\s+", "_", clean.strip())
    if len(clean) > max_len:
        clean = clean[:max_len]
    return clean or "audit"


def write_markdown_artifact(
    content: str,
    output_path: Path,
) -> Path:
    """创建UTF-8 MD文件。父目录自动创建，已有文件覆盖。

    Args:
        content: Markdown 内容
        output_path: 写入路径

    Returns:
        写入后的绝对路径

    Raises:
        OSError: 写入失败
    """
    p = Path(output_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())

    return p


def suggest_output_dir() -> Path:
    """建议输出目录（项目外可交付）。"""
    return Path(__file__).resolve().parent.parent / "output"
