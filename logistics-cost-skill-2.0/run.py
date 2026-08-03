#!/usr/bin/env python3
"""物流成本核算 — simple-v2.1 单一入口。

用法:
  python run.py --ai-json <path> [--weight-value N] [--link URL] [--compact]
  echo '$JSON' | python run.py --stdin [--compact]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from logistics_cost.ai_schema import validate, to_estimate_inputs
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import build_user_weight


def _compact_output(result: dict) -> dict:
    """只返回最终格式化所需字段。"""
    compact = {"status": result.get("status", "error")}
    for mode in ("normal", "conservative"):
        item = result.get(mode) or {}
        compact[mode] = {
            "packaged_size_cm": item.get("packaged_size_cm", []),
            "packaged_weight_kg": item.get("packaged_weight_kg", 0),
            "chargeable_weight_kg": item.get("chargeable_weight_kg", 0),
            "provider_costs": item.get("provider_costs", {}),
            "recommended_provider": item.get("recommended_provider", ""),
            "recommended_cost_rmb": item.get("recommended_cost_rmb", 0),
            "head_cost_cny": item.get("head_cost_cny", 0),
            "service_fee_cny": item.get("service_fee_cny", 0),
        }
    compact["needs_review"] = result.get("needs_review", False)
    compact["review_reasons"] = (result.get("review_reasons") or [])[:3]
    return compact


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="物流成本核算 simple-v2.1")
    p.add_argument("--ai-json", type=Path, metavar="PATH", help="Codex AI JSON 文件")
    p.add_argument("--stdin", action="store_true", help="从标准输入读取 JSON")
    p.add_argument("--compact", action="store_true", help="简洁输出模式")
    p.add_argument("--weight-value", type=float, help="用户商品净重")
    p.add_argument("--weight-unit", choices=("g", "kg"), default="g")
    p.add_argument("--weight-trust", default="可信",
                   choices=("可信", "约值", "未核实", "参考", "低置信", "多规格未知", "未提供"))
    p.add_argument("--link", help="商品链接(仅保存, 不访问)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    uw = build_user_weight(args.weight_value, args.weight_unit, args.weight_trust)
    debug = "--debug" in (argv or [])

    if args.stdin:
        raw = json.loads(sys.stdin.read())
    elif args.ai_json:
        try:
            with open(args.ai_json, encoding="utf-8") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
    else:
        print(json.dumps({"status": "error", "error": "需要 --ai-json 或 --stdin"}, ensure_ascii=False), file=sys.stderr)
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

    result["ai_meta"] = ai_meta

    if args.compact:
        output = _compact_output(result)
    else:
        output = result
    print(json.dumps(output, ensure_ascii=False, indent=None, default=str))

    if result.get("status") == "calculated":
        if debug:
            n = result.get("normal", {})
            c = result.get("conservative", {})
            print(f"\n正常档: {n.get('head_cost_cny', 0):.1f} 元  保守档: {c.get('head_cost_cny', 0):.1f} 元", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
