#!/usr/bin/env python3
"""物流成本核算 — simple-v2.2 单一入口 (OUTPUT_CONTRACT 2026-08-04-v1)。

用法:
  python run.py --ai-json <path> [--weight-value N] [--link URL] [--compact]
  echo '$JSON' | python run.py --stdin [--compact] [--render-markdown]
  echo '$ENVELOPE_JSON' | python run.py --stdin --render-markdown
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from logistics_cost.ai_schema import validate, to_estimate_inputs
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import build_user_weight
from logistics_cost.output_renderer import render_head_only, render_profit


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
    p = argparse.ArgumentParser(description="物流成本核算 simple-v2.2")
    p.add_argument("--ai-json", type=Path, metavar="PATH", help="Codex AI JSON 文件")
    p.add_argument("--stdin", action="store_true", help="从标准输入读取 JSON")
    p.add_argument("--compact", action="store_true", help="简洁输出模式 (JSON)")
    p.add_argument("--render-markdown", action="store_true", help="确定性 Markdown 渲染 (输出合同 2026-08-04-v1)")
    p.add_argument("--weight-value", type=float, help="用户商品净重")
    p.add_argument("--weight-unit", choices=("g", "kg"), default="g")
    p.add_argument("--weight-trust", default="可信",
                   choices=("可信", "约值", "未核实", "参考", "低置信", "多规格未知", "未提供"))
    p.add_argument("--link", help="商品链接(仅保存, 不访问)")
    p.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    uw = build_user_weight(args.weight_value, args.weight_unit, args.weight_trust)

    # 读取输入 (信封模式或裸 AI JSON)
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

    # ---- 信封模式解包 ----
    mode = raw.get("mode", "head_only") if isinstance(raw, dict) else "head_only"
    product_display = raw.get("product_display", {}) if isinstance(raw, dict) else {}
    profit_parameters = raw.get("profit_parameters") if isinstance(raw, dict) else None
    # AI JSON 可能在信封的 "ai" 字段或根对象本身
    ai_data = raw.get("ai", raw) if isinstance(raw, dict) else raw

    try:
        ai = validate(ai_data)
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
        product_link=args.link or getattr(ai, "product_link", ""),
        user_weight=uw,
    )

    result["ai_meta"] = ai_meta

    # ---- 输出决策 ----
    if args.render_markdown:
        if not product_display:
            # 从 AI 结果和 estimate 结果回填基本显示信息
            product_display = {
                "title": summary.get("product_type", "未知商品"),
                "quantity": summary.get("quantity", 1),
                "unit": summary.get("unit", "件"),
                "purchase_price_rmb": product_display.get("purchase_price_rmb"),
                "domestic_freight_rmb": product_display.get("domestic_freight_rmb"),
                "normal_packaging": product_display.get("normal_packaging", "标准包装"),
                "conservative_packaging": product_display.get("conservative_packaging", "保守包装"),
                "confidence": summary.get("confidence", "low"),
            }

        if mode == "profit" and profit_parameters:
            output_md = render_profit(
                result=result,
                product_display=product_display,
                exchange_rate=float(profit_parameters.get("exchange_rate", 6.7716)),
                tail_fee_usd=float(profit_parameters.get("tail_fee_usd", 7)),
                target_profit_markup_percent=float(profit_parameters.get("target_profit_markup_percent", 25)),
                activity_reserve_percent=float(profit_parameters.get("activity_reserve_percent", 15)),
            )
        else:
            output_md = render_head_only(
                result=result,
                product_display=product_display,
            )
        print(output_md)
    elif args.compact:
        output = _compact_output(result)
        print(json.dumps(output, ensure_ascii=False, indent=None, default=str))
    else:
        output = result
        print(json.dumps(output, ensure_ascii=False, indent=None, default=str))

    if result.get("status") == "calculated":
        if args.debug:
            n = result.get("normal", {})
            c = result.get("conservative", {})
            print(f"\n正常档: {n.get('head_cost_cny', 0):.1f} 元  保守档: {c.get('head_cost_cny', 0):.1f} 元", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
