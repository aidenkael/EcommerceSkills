"""运行审计 — 轻量、确定性的审计记录（默认仅内存，显式请求才写文件）。"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .product_request import ProductRequest


def _get_git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


@dataclass
class AuditRecord:
    """一次完整运行的审计记录。"""
    request_id: str = ""
    product_signature: str = ""
    title: str = ""
    selected_sku: str = ""
    quantity: int = 1

    # 事实及其来源
    facts: list[dict] = field(default_factory=list)

    # AI 数据
    ai_data_raw: dict = field(default_factory=dict)
    ai_data_arbitrated: dict = field(default_factory=dict)

    # 校准
    calibration_hit: bool = False
    calibration_case_id: str = ""

    # 计算结果
    result: dict = field(default_factory=dict)
    run_stdout: str = ""

    # 时间与版本
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    git_sha: str = field(default_factory=_get_git_sha)


def build_audit_record(req: ProductRequest) -> AuditRecord:
    """从当前 ProductRequest 构建审计记录。"""
    return AuditRecord(
        request_id=req.request_id,
        product_signature=req.product_signature,
        title=req.title,
        selected_sku=req.selected_sku,
        quantity=req.quantity,
        facts=[{"field": f.field, "value": f.value, "source": f.source, "confidence": f.confidence, "location": f.location} for f in req.facts],
        ai_data_raw=dict(req.ai_data_raw),
        ai_data_arbitrated=dict(req.ai_data_arbitrated),
        calibration_hit=req.calibration_hit,
        calibration_case_id=req.calibration_case_id,
        result=dict(req.result),
        run_stdout=req.run_stdout,
    )


def render_audit_markdown(audit: AuditRecord) -> str:
    """将审计记录渲染为 Markdown 文件。"""
    lines = [
        f"# 物流核算审计记录",
        f"",
        f"## 请求身份",
        f"- request_id: {audit.request_id}",
        f"- product_signature: {audit.product_signature}",
        f"- 标题: {audit.title}",
        f"- SKU: {audit.selected_sku}",
        f"- 数量: {audit.quantity}",
        f"- 运行时间: {audit.created_at}",
        f"- Git SHA: {audit.git_sha or 'N/A'}",
        f"",
        f"## 商品事实",
    ]

    if audit.facts:
        for f in audit.facts:
            src_label = {
                "user_confirmed": "用户确认",
                "merchant_text": "商家文字",
                "image_visible": "图片可见",
                "calibrated": "精确校准",
                "ai_inferred": "AI推测",
            }.get(f["source"], f["source"])
            lines.append(f"- {f['field']}: {f['value']}（来源: {src_label}, 置信度: {f['confidence']}）")
    else:
        lines.append("- 无记录")

    lines.append("")
    lines.append(f"## 校准")
    lines.append(f"- 是否命中: {'是' if audit.calibration_hit else '否'}")
    if audit.calibration_case_id:
        lines.append(f"- 案例: {audit.calibration_case_id}")

    lines.append("")
    lines.append(f"## 计算结果")
    result = audit.result or {}
    normal = result.get("normal") or {}
    conservative = result.get("conservative") or {}
    lines.append(f"- 状态: {result.get('status', 'N/A')}")
    lines.append(f"- 正常档计费重: {round(float(normal.get('chargeable_weight_kg', 0)) * 1000)}g")
    lines.append(f"- 保守档计费重: {round(float(conservative.get('chargeable_weight_kg', 0)) * 1000)}g")

    if result.get("_request_id"):
        r_id = result.get("_request_id", "")
        lines.append(f"- 绑定 request_id: {r_id}")
        lines.append(f"- 身份一致: {'是' if r_id == audit.request_id else '否'}")

    lines.append("")
    lines.append(f"## Renderer 输出")
    lines.append(f"```")
    lines.append(audit.run_stdout or "(无)")
    lines.append(f"```")
    lines.append(f"")

    return "\n".join(lines)
