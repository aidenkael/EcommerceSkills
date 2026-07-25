#!/usr/bin/env python3
"""物流成本核算 — simple-v2.1 单一入口。

用法:
  python run.py --ai-json <path> [--weight-value N] [--weight-unit g|kg] [--weight-trust 可信] [--link URL] [--pretty]

流程:
  AI JSON 文件 (Codex 输出)
    → logistics_cost.ai_schema.to_estimate_inputs()
    → logistics_cost.estimator.estimate()
      → evidence_resolver + soft_goods_rules + weight_rules
      → calculator.calc_head_cost()
    → 输出正常档/保守档/头程/置信度/复核标记

默认: 不访问 1688 链接, 不读取历史数据, 不建立价格库
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from logistics_cost.ai_schema import validate, to_estimate_inputs
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import build_user_weight


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="物流成本核算 simple-v2.1")
    p.add_argument("--ai-json", type=Path, required=True, metavar="PATH",
                   help="Codex AI JSON 文件")
    p.add_argument("--weight-value", type=float, help="用户商品净重")
    p.add_argument("--weight-unit", choices=("g", "kg"), default="g")
    p.add_argument("--weight-trust", default="可信",
                   choices=("可信", "约值", "未核实", "参考", "低置信", "多规格未知", "未提供"))
    p.add_argument("--link", help="商品链接(仅保存, 不访问)")
    p.add_argument("--pretty", action="store_true", help="美化 JSON 输出")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    uw = build_user_weight(args.weight_value, args.weight_unit, args.weight_trust)

    try:
        with open(args.ai_json, encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    try:
        ai = validate(raw)
    except ValueError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    summary, evidence, scenarios, ai_meta = to_estimate_inputs(ai)
    if args.link:
        summary["product_link"] = args.link

    result = estimate(
        product_summary=summary,
        raw_evidence=evidence,
        packaging_scenarios=scenarios,
        product_link=args.link or ai.product_link,
        user_weight=uw,
    )

    # 附加 AI 元数据
    result["ai_meta"] = ai_meta

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, default=str))

    if result.get("status") == "calculated":
        n = result.get("normal", {})
        c = result.get("conservative", {})
        print(f"\n正常档: {n.get('head_cost_cny', 0):.1f} 元  保守档: {c.get('head_cost_cny', 0):.1f} 元", file=sys.stderr)
        if n.get("soft_volume_ignored"):
            print(f"  [软品] {n.get('soft_volume_warning', '')[:100]}", file=sys.stderr)
        if result.get("needs_review"):
            reasons = "; ".join(result.get("review_reasons", [])[:3])
            print(f"  [复核] {reasons}", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
