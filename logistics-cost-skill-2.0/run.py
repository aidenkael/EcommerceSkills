#!/usr/bin/env python3
"""物流成本核算 — simple-v2.2 单一入口 (OUTPUT_CONTRACT 2026-08-04-v2)。"""
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
from logistics_cost.session_preferences import (
    resolve_mode, get_profit_params as get_saved_profit_params,
    update_profit_params, validate_profit_params,
)
from logistics_cost.product_request import create_product_request, ProductRequest
from logistics_cost.request_freshness_guard import validate_request_freshness, RequestFreshnessViolation
from logistics_cost.request_audit import build_audit_record, render_audit_markdown
from logistics_cost.artifact_delivery import write_markdown_artifact


def _compact_output(result: dict) -> dict:
    compact = {"status": result.get("status", "error")}
    for m in ("normal", "conservative"):
        item = result.get(m) or {}
        compact[m] = {
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


def _parser():
    p = argparse.ArgumentParser(description="物流成本核算 simple-v2.2")
    p.add_argument("--ai-json", type=Path, metavar="PATH")
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--compact", action="store_true")
    p.add_argument("--render-markdown", action="store_true")
    p.add_argument("--audit-md", type=Path, metavar="PATH", help="生成审计 Markdown 文件")
    p.add_argument("--prefs-path", type=Path, metavar="PATH", help="偏好文件路径(测试用)")
    p.add_argument("--weight-value", type=float)
    p.add_argument("--weight-unit", choices=("g", "kg"), default="g")
    p.add_argument("--weight-trust", default="可信",
                   choices=("可信", "约值", "未核实", "参考", "低置信", "多规格未知", "未提供"))
    p.add_argument("--link")
    p.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    return p


def _resolve_envelope(raw):
    pd = raw.get("product_display", {}) if isinstance(raw, dict) else {}
    ai = raw.get("ai", raw) if isinstance(raw, dict) else raw
    pp = raw.get("profit_parameters") if isinstance(raw, dict) else None
    em = raw.get("mode") if isinstance(raw, dict) else None
    facts = raw.get("facts") if isinstance(raw, dict) else None
    return pd, ai, pp, em, facts


def _resolve_title(pd, ai):
    return pd.get("title") or ai.get("product_title") or ai.get("product_type") or ""


def _resolve_sku(pd, ai):
    return pd.get("selected_sku") or ai.get("selected_sku") or ""


def _resolve_quantity(pd, ai):
    q = pd.get("quantity")
    if q is not None:
        return int(q)
    q = ai.get("quantity")
    if q is not None:
        return int(q)
    return 1


def _dimension_scope_to_field(scope: str) -> str:
    """AI dimension_scope → 统一事实 field。"""
    mapping = {
        "shipping_package_size": "shipping_package_size",
        "product_size": "product_size",
        "display_size": "display_size",
    }
    return mapping.get(scope, "unknown_size")


def main(argv=None):
    args = _parser().parse_args(argv)

    if args.prefs_path:
        import logistics_cost.session_preferences as sp
        sp._prefs_path = lambda: Path(args.prefs_path)

    if args.stdin:
        raw = json.loads(sys.stdin.read())
    elif args.ai_json:
        try:
            raw = json.loads(open(args.ai_json, encoding="utf-8").read())
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
    else:
        print(json.dumps({"status": "error", "error": "需要 --ai-json 或 --stdin"}, ensure_ascii=False), file=sys.stderr)
        return 2

    product_display, ai_data, profit_parameters, envelope_mode, envelope_facts = _resolve_envelope(raw)

    # ---- 模式 ----
    mode, mode_error = resolve_mode(envelope_mode)
    if mode_error:
        print(json.dumps({"status": "error", "error": mode_error}, ensure_ascii=False), file=sys.stderr)
        return 2

    # ---- 利润参数 ----
    if profit_parameters:
        update_profit_params(profit_parameters)
    if mode == "profit":
        merged = dict(get_saved_profit_params())
        if profit_parameters:
            merged.update(profit_parameters)
        vp, missing = validate_profit_params(merged)
        if missing:
            print(json.dumps({"status": "error", "error": "profit_parameters_required", "missing": missing}, ensure_ascii=False), file=sys.stderr)
            return 2
        profit_parameters = vp

    # ---- ProductRequest ----
    title = _resolve_title(product_display, ai_data)
    sku = _resolve_sku(product_display, ai_data)
    quantity = _resolve_quantity(product_display, ai_data)

    req = create_product_request(
        title=title, selected_sku=sku, quantity=quantity,
        unit=product_display.get("unit", "件"),
        image_path=product_display.get("image_path", ""),
        image_fingerprint=product_display.get("image_fingerprint", ""),
        purchase_price_rmb=product_display.get("purchase_price_rmb"),
        domestic_freight_rmb=product_display.get("domestic_freight_rmb"),
    )
    req.ai_data_raw = dict(ai_data)

    # ---- 事实导入 ----
    req.import_envelope_facts(envelope_facts)
    for field_key, disp_key, src in [
        ("net_weight", "user_weight_g", "user_confirmed"),
        ("purchase_price_rmb", "purchase_price_rmb", "user_confirmed"),
        ("domestic_freight_rmb", "domestic_freight_rmb", "user_confirmed"),
    ]:
        if product_display.get(disp_key) is not None:
            unit = "g" if "weight" in field_key else ""
            req.add_fact(field_key, product_display[disp_key], src, unit=unit, confidence="high")

    # AI 候选重量（默认 ai_inferred）
    ai_net = ai_data.get("ai_net_weight_kg")
    if ai_net is not None:
        req.add_fact("net_weight", ai_net, "ai_inferred", unit="kg", confidence=ai_data.get("confidence", "medium"))

    # AI 候选尺寸按 dimension_scope 映射到正确 field
    ai_dims = ai_data.get("ai_package_size_cm")
    if ai_dims:
        scope = ai_data.get("dimension_scope", "unknown")
        field = _dimension_scope_to_field(scope)
        req.add_fact(field, list(ai_dims), "ai_inferred", unit="cm", scope=scope, confidence=ai_data.get("confidence", "medium"))

    # ---- 解析事实 ----
    resolved_weight = req.get_resolved_net_weight()
    resolved_dims = req.get_resolved_dimensions()

    # ---- 精确校准 ----
    ai_data_working = dict(ai_data)
    if sku and title:
        ch = resolve_exact_calibration(title, sku, quantity)
        if ch:
            ai_data_working = apply_calibration_override(dict(ai_data_working), ch)
            req.calibration_hit = True
            req.calibration_case_id = ch.get("case_id", "")

    # ---- 高优先级尺寸事实覆盖（校准命中时不覆盖 ai_inferred 来源） ----
    if resolved_dims["dims_cm"]:
        dims = resolved_dims["dims_cm"]
        scope = resolved_dims["scope"]
        src = resolved_dims["source"]
        # ai_inferred 不覆盖校准结果
        if src != "ai_inferred" or not req.calibration_hit:
            if scope == "shipping_package_size":
                ai_data_working["ai_package_size_cm"] = list(dims)
                ai_data_working["conservative_package_size_cm"] = list(dims)
                ai_data_working["dimension_scope"] = "shipping_package_size"
            else:
                ai_data_working["ai_package_size_cm"] = list(dims)
                ai_data_working["dimension_scope"] = scope

    # ---- 包装仲裁 ----
    ai_data_working = arbitrate_packaging_candidate(
        ai_data_working, exact_calibration_applied=req.calibration_hit,
    )
    req.ai_data_arbitrated = dict(ai_data_working)

    # ---- 用户确认重量进入可信重量入口 ----
    uw = build_user_weight(args.weight_value, args.weight_unit, args.weight_trust)
    if resolved_weight["value_kg"] is not None and uw is None:
        # 仅 user_confirmed/merchant_text 来源使用可信重量入口；校准不触发增量
        src = resolved_weight["source"]
        if src in ("user_confirmed", "merchant_text"):
            trust = "可信" if src == "user_confirmed" else "约值"
            uw = UserWeight(resolved_weight["value_kg"] * 1000, "g", trust)

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
        product_summary=summary, raw_evidence=evidence, packaging_scenarios=scenarios,
        product_link=args.link or getattr(ai, "product_link", ""), user_weight=uw,
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

    # ---- 渲染 ----
    if args.render_markdown:
        if not product_display:
            product_display = {
                "title": summary.get("product_type", "未知商品"),
                "quantity": summary.get("quantity", 1), "unit": summary.get("unit", "件"),
                "purchase_price_rmb": product_display.get("purchase_price_rmb"),
                "domestic_freight_rmb": product_display.get("domestic_freight_rmb"),
                "normal_packaging": product_display.get("normal_packaging", "标准包装"),
                "conservative_packaging": product_display.get("conservative_packaging", "保守包装"),
                "confidence": summary.get("confidence", "low"),
            }

        if mode == "profit" and profit_parameters:
            output_md = render_profit(
                result=result, product_display=product_display,
                exchange_rate=float(profit_parameters["exchange_rate"]),
                tail_fee_usd=float(profit_parameters["tail_fee_usd"]),
                target_profit_markup_percent=float(profit_parameters["target_profit_markup_percent"]),
                activity_reserve_percent=float(profit_parameters["activity_reserve_percent"]),
            )
        else:
            output_md = render_head_only(result=result, product_display=product_display)

        # 输出合同守卫
        try:
            validate_rendered_output(output_md, mode)
        except OutputContractViolation as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2

        # 请求新鲜度
        try:
            validate_request_freshness(request=req, result=result)
        except RequestFreshnessViolation as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2

        # 设置 run_stdout（在审计构建之前）
        req.run_stdout = output_md

        # 审计文件
        if args.audit_md:
            audit = build_audit_record(req)
            audit_md = render_audit_markdown(audit)
            try:
                write_markdown_artifact(audit_md, args.audit_md)
            except OSError as exc:
                print(json.dumps({"status": "error", "error": f"审计文件写入失败: {exc}"}, ensure_ascii=False), file=sys.stderr)
                return 2

        print(output_md)

    elif args.compact:
        print(json.dumps(_compact_output(result), ensure_ascii=False, indent=None, default=str))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=None, default=str))

    if result.get("status") == "calculated":
        if args.debug:
            if req.calibration_hit:
                print(f"calibration_case={req.calibration_case_id}", file=sys.stderr)
            n = result.get("normal", {})
            c = result.get("conservative", {})
            print(f"\n正常档: {n.get('head_cost_cny', 0):.1f} 元  保守档: {c.get('head_cost_cny', 0):.1f} 元", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
