#!/usr/bin/env python3
"""物流成本核算 — simple-v2.2 单一入口 (OUTPUT_CONTRACT 2026-08-04-v2)。

用法:
  python run.py --ai-json <path> [--audit-md PATH] [--weight-value N] [--link URL] [--compact]
  echo '$JSON' | python run.py --stdin [--audit-md PATH] [--compact] [--render-markdown]
  echo '$ENVELOPE_JSON' | python run.py --stdin --render-markdown [--audit-md PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from logistics_cost.ai_schema import validate, to_estimate_inputs
from logistics_cost.estimator import estimate
from logistics_cost.weight_rules import build_user_weight, UserWeight
from logistics_cost.output_renderer import render_head_only, render_profit
from logistics_cost.calibration_resolver import resolve_exact_calibration, apply_calibration_override
from logistics_cost.output_contract_guard import validate_rendered_output, OutputContractViolation
from logistics_cost.packaging_arbitrator import arbitrate_packaging_candidate
from logistics_cost.session_preferences import resolve_mode, get_profit_params as get_saved_profit_params, update_profit_params
from logistics_cost.product_request import create_product_request, ProductRequest
from logistics_cost.request_freshness_guard import validate_request_freshness, RequestFreshnessViolation
from logistics_cost.request_audit import build_audit_record, render_audit_markdown
from logistics_cost.artifact_delivery import write_markdown_artifact


def _compact_output(result: dict) -> dict:
    compact = {"status": result.get("status", "error")}
    for mode_key in ("normal", "conservative"):
        item = result.get(mode_key) or {}
        compact[mode_key] = {
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
    p.add_argument("--render-markdown", action="store_true", help="确定性 Markdown 渲染 (输出合同 2026-08-04-v2)")
    p.add_argument("--audit-md", type=Path, metavar="PATH", help="生成审计 Markdown 文件")
    p.add_argument("--weight-value", type=float, help="用户商品净重")
    p.add_argument("--weight-unit", choices=("g", "kg"), default="g")
    p.add_argument("--weight-trust", default="可信",
                   choices=("可信", "约值", "未核实", "参考", "低置信", "多规格未知", "未提供"))
    p.add_argument("--link", help="商品链接(仅保存, 不访问)")
    p.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    return p


def _resolve_envelope(raw: dict) -> tuple[dict, dict, dict | None, str | None]:
    """解包信封。"""
    product_display = raw.get("product_display", {}) if isinstance(raw, dict) else {}
    profit_parameters = raw.get("profit_parameters") if isinstance(raw, dict) else None
    ai_data = raw.get("ai", raw) if isinstance(raw, dict) else raw
    envelope_mode = raw.get("mode") if isinstance(raw, dict) else None
    return (product_display, ai_data, profit_parameters, envelope_mode)


def _resolve_title(product_display: dict, ai_data: dict) -> str:
    title = product_display.get("title") or ""
    if not title:
        title = ai_data.get("product_title") or ""
    if not title:
        title = ai_data.get("product_type") or ""
    return title


def _resolve_sku(product_display: dict, ai_data: dict) -> str:
    sku = product_display.get("selected_sku") or ""
    if not sku:
        sku = ai_data.get("selected_sku") or ""
    return sku


def _resolve_quantity(product_display: dict, ai_data: dict) -> int:
    qty = product_display.get("quantity")
    if qty is not None:
        return int(qty)
    qty = ai_data.get("quantity")
    if qty is not None:
        return int(qty)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    # 读取输入
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

    product_display, ai_data, profit_parameters, envelope_mode = _resolve_envelope(raw)

    # ---- 模式解析 ----
    mode, mode_error = resolve_mode(envelope_mode)
    if mode_error:
        print(json.dumps({"status": "error", "error": mode_error}, ensure_ascii=False), file=sys.stderr)
        return 2

    # ---- 利润参数持久化 ----
    if profit_parameters:
        update_profit_params(profit_parameters)
    elif mode == "profit":
        saved = get_saved_profit_params()
        if any(v is not None for v in saved.values()):
            profit_parameters = saved

    # ---- 创建 ProductRequest ----
    title = _resolve_title(product_display, ai_data)
    sku = _resolve_sku(product_display, ai_data)
    quantity = _resolve_quantity(product_display, ai_data)

    req = create_product_request(
        title=title,
        selected_sku=sku,
        quantity=quantity,
        unit=product_display.get("unit", "件"),
        image_path=product_display.get("image_path", ""),
        image_fingerprint=product_display.get("image_fingerprint", ""),
        purchase_price_rmb=product_display.get("purchase_price_rmb"),
        domestic_freight_rmb=product_display.get("domestic_freight_rmb"),
    )

    req.ai_data_raw = dict(ai_data)

    # ---- 用户/商家事实接入 ----
    _apply_facts_to_request(req, product_display, ai_data)

    # ---- 精确校准 ----
    ai_data_working = dict(ai_data)
    if sku and title:
        calibration_hit_case = resolve_exact_calibration(title, sku, quantity)
        if calibration_hit_case:
            ai_data_working = apply_calibration_override(dict(ai_data_working), calibration_hit_case)
            req.calibration_hit = True
            req.calibration_case_id = calibration_hit_case.get("case_id", "")

    # ---- 包装仲裁 ----
    ai_data_working = arbitrate_packaging_candidate(
        ai_data_working,
        exact_calibration_applied=req.calibration_hit,
    )
    req.ai_data_arbitrated = dict(ai_data_working)

    # ---- 用户确认重量接入 ----
    uw = build_user_weight(args.weight_value, args.weight_unit, args.weight_trust)
    w_val, w_source = req.get_user_weight_info()
    if w_val is not None and uw is None:
        uw = UserWeight(w_val, "g", "可信" if w_source == "user_confirmed" else "约值")

    # ---- validate + estimate ----
    try:
        ai = validate(ai_data_working)
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
    result["_request_id"] = req.request_id
    result["_product_signature"] = req.product_signature
    result["_title"] = req.title
    result["_selected_sku"] = req.selected_sku
    result["_quantity"] = req.quantity

    if req.calibration_hit:
        result["calibration_applied"] = True
        result["calibration_case_id"] = req.calibration_case_id

    req.result = dict(result)

    # ---- 输出 ----
    if args.render_markdown:
        if not product_display:
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

        # 输出合同守卫
        try:
            validate_rendered_output(output_md, mode)
        except OutputContractViolation as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2

        # 请求新鲜度校验
        try:
            validate_request_freshness(
                request_id=req.request_id,
                product_signature=req.product_signature,
                title=req.title,
                selected_sku=req.selected_sku,
                quantity=req.quantity,
                result_request_id=result.get("_request_id", ""),
                result_signature=result.get("_product_signature", ""),
                result_title=result.get("_title", ""),
                result_sku=result.get("_selected_sku", ""),
                result_quantity=result.get("_quantity", 0),
            )
        except RequestFreshnessViolation as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2

        req.run_stdout = output_md
        print(output_md)

        # 审计文件
        if args.audit_md:
            audit = build_audit_record(req)
            audit_md = render_audit_markdown(audit)
            try:
                write_markdown_artifact(audit_md, args.audit_md)
            except OSError as exc:
                print(json.dumps({"status": "error", "error": f"审计文件写入失败: {exc}"}, ensure_ascii=False), file=sys.stderr)
                return 2

    elif args.compact:
        output = _compact_output(result)
        print(json.dumps(output, ensure_ascii=False, indent=None, default=str))
    else:
        output = result
        print(json.dumps(output, ensure_ascii=False, indent=None, default=str))

    if result.get("status") == "calculated":
        if args.debug:
            if req.calibration_hit:
                print(f"calibration_case={req.calibration_case_id}", file=sys.stderr)
            n = result.get("normal", {})
            c = result.get("conservative", {})
            print(f"\n正常档: {n.get('head_cost_cny', 0):.1f} 元  保守档: {c.get('head_cost_cny', 0):.1f} 元", file=sys.stderr)
        return 0
    return 2


def _apply_facts_to_request(req: ProductRequest, product_display: dict, ai_data: dict) -> None:
    """将信封中的用户/商家事实加入 ProductRequest。"""
    # 用户确认（从 product_display 的显式字段）
    for field, src_key in [
        ("title", "title"),
        ("selected_sku", "selected_sku"),
        ("quantity", "quantity"),
    ]:
        if src_key in product_display and product_display[src_key] is not None:
            req.add_fact(field, product_display[src_key], "user_confirmed", "high")

    for field, src_key in [
        ("purchase_price_rmb", "purchase_price_rmb"),
        ("domestic_freight_rmb", "domestic_freight_rmb"),
    ]:
        if product_display.get(src_key) is not None:
            req.add_fact(field, product_display[src_key], "user_confirmed", "high")

    # 商家规格（从 ai_data）
    if ai_data.get("ai_net_weight_kg") is not None:
        req.add_fact("net_weight_kg", ai_data["ai_net_weight_kg"], "merchant_text", "medium")
    if ai_data.get("ai_package_size_cm"):
        req.add_fact("product_size_cm", list(ai_data["ai_package_size_cm"]), "merchant_text", "medium")


if __name__ == "__main__":
    raise SystemExit(main())
