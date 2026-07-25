"""头程金额反馈命令行入口；不根据金额伪造真实尺寸或重量。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from logistics_cost.config import DEFAULT_CONFIG_PATH, load_config
from logistics_cost.feedback import (
    FEEDBACK_FIELDS,
    MODE_NOTE,
    build_feedback_record,
    deduplicate_feedback_rows,
    generate_accuracy_report,
    read_feedback,
    rebuild_diagnoses,
    validate_profile,
)
from logistics_cost.storage import (
    append_csv,
    archive_local_image,
    ensure_csv,
    read_csv,
    write_csv,
    write_json,
)


BASE_DIR = Path(__file__).resolve().parent
FEEDBACK_PATH = BASE_DIR / "data" / "head_cost_feedback.csv"
ESTIMATE_PATH = BASE_DIR / "data" / "estimate_records.csv"
HEAD_ESTIMATE_PATH = BASE_DIR / "data" / "head_cost_estimates.jsonl"
REPORT_PATH = BASE_DIR / "output" / "accuracy_report.csv"
PROFILES_PATH = BASE_DIR / "data" / "package_profiles.json"
PRODUCT_IMAGES_DIR = BASE_DIR / "data" / "product_images"


def ensure_storage() -> None:
    ensure_csv(FEEDBACK_PATH, FEEDBACK_FIELDS)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRODUCT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)



def _head_estimate_context(estimate_id: str, path: Path = HEAD_ESTIMATE_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    match: dict[str, Any] = {}
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                candidate = json.loads(line)
                if candidate.get("estimate_id") == estimate_id:
                    match = candidate
    if not match:
        return {}
    normal = match.get("normal") or {}
    conservative = match.get("conservative") or {}
    dimensions = normal.get("packaged_size_cm") or ["", "", ""]
    accepted = match.get("accepted_evidence") or {}
    rejected = match.get("rejected_evidence") or {}
    summary = match.get("product_summary") or {}
    return {
        "estimate_id": estimate_id,
        "product_id": str(match.get("product_id") or estimate_id),
        "image_path": str(match.get("image_path") or ""),
        "product_type": str(match.get("product_type") or ""),
        "category_type": str(match.get("category_type") or ""),
        "product_link": str(match.get("product_link") or summary.get("product_link") or ""),
        "quantity": str(match.get("quantity") or summary.get("quantity") or 1),
        "shape_type": str(summary.get("shape_type") or ""),
        "size_class": str(match.get("size_class") or summary.get("size_class") or ""),
        "foldability": str(match.get("foldability") or summary.get("foldability") or ""),
        "rigidity": str(summary.get("rigidity") or ""),
        "requires_shape_retention": str(bool(summary.get("requires_shape_retention"))).lower(),
        "packaging_profile_key": str(match.get("packaging_profile_key") or summary.get("packaging_profile_key") or ""),
        "ai_product_summary": json.dumps(match.get("product_summary") or {}, ensure_ascii=False),
        "accepted_dimensions": json.dumps(accepted.get("dimensions"), ensure_ascii=False),
        "accepted_weight": json.dumps(accepted.get("weight"), ensure_ascii=False),
        "rejected_evidence": json.dumps(rejected, ensure_ascii=False),
        "normal_packaged_size": json.dumps(normal.get("packaged_size_cm") or [], ensure_ascii=False),
        "conservative_packaged_size": json.dumps(conservative.get("packaged_size_cm") or [], ensure_ascii=False),
        "packaging_method": str(normal.get("method") or ""),
        "estimated_length_cm": str(dimensions[0]),
        "estimated_width_cm": str(dimensions[1]),
        "estimated_height_cm": str(dimensions[2]),
        "estimated_actual_weight_kg": str(normal.get("packaged_weight_kg") or ""),
        "estimated_volume_weight_kg": str(normal.get("volume_weight_kg") or ""),
        "estimated_head_cost": str(normal.get("head_cost_cny") or ""),
        "conservative_head_cost": str(conservative.get("head_cost_cny") or ""),
    }

def _estimate_context(estimate_id: str, head_estimate_path: Path = HEAD_ESTIMATE_PATH) -> dict[str, str]:
    if not estimate_id:
        return {}
    matches = [row for row in read_csv(ESTIMATE_PATH) if row.get("estimate_id") == estimate_id]
    normal = next((row for row in matches if row.get("estimate_mode") == "normal"), matches[0] if matches else {})
    conservative = next((row for row in matches if row.get("estimate_mode") == "conservative"), {})
    if not normal:
        return _head_estimate_context(estimate_id, head_estimate_path)
    normal = dict(normal)
    for source, target in (
        ("length_cm", "estimated_length_cm"), ("width_cm", "estimated_width_cm"),
        ("height_cm", "estimated_height_cm"), ("actual_weight_kg", "estimated_actual_weight_kg"),
        ("volume_weight_kg", "estimated_volume_weight_kg"),
    ):
        normal[target] = normal.get(source, "")
    normal["conservative_head_cost"] = conservative.get("estimated_head_cost", "")
    return normal


def _archive(record: dict[str, str]) -> None:
    source = record.get("image_path") or record.get("product_link") or ""
    archived = archive_local_image(source, PRODUCT_IMAGES_DIR, record["product_id"])
    if archived:
        record["image_path"] = Path(archived).relative_to(BASE_DIR).as_posix()
        if Path(source).is_file():
            record["product_link"] = ""


def append_feedback(raw: dict[str, Any], head_estimate_path: Path = HEAD_ESTIMATE_PATH) -> dict[str, str]:
    history = deduplicate_feedback_rows(read_feedback(FEEDBACK_PATH))
    estimate_id = str(raw.get("estimate_id") or "").strip()
    if estimate_id and any(row.get("estimate_id") == estimate_id for row in history):
        raise ValueError(f"同一estimate_id已存在反馈: {estimate_id}")
    estimate_context = _estimate_context(estimate_id, head_estimate_path)
    context = {key: value for key, value in raw.items() if value not in (None, "")}
    if estimate_context:
        context.update({key: value for key, value in estimate_context.items() if value not in (None, "")})
        for key in ("actual_head_cost", "notes", "error_reason_category", "feedback_id", "date"):
            if raw.get(key) not in (None, ""):
                context[key] = raw[key]
    record = build_feedback_record(context, load_config(), history)
    _archive(record)
    append_csv(FEEDBACK_PATH, record, FEEDBACK_FIELDS)
    generate_accuracy_report(FEEDBACK_PATH, REPORT_PATH)
    return record


def add_interactive(head_estimate_path: Path = HEAD_ESTIMATE_PATH) -> dict[str, str]:
    def ask(label: str, required: bool = False) -> str:
        while True:
            value = input(f"{label}: ").strip()
            if value or not required:
                return value
            print("此项不能为空。")

    estimate_id = ask("estimate_id（可为空）")
    raw = {"estimate_id": estimate_id}
    if not estimate_id:
        raw.update({
            "product_id": ask("product_id（可为空）"),
            "product_link": ask("product_link或本地图片路径", True),
            "category_type": ask("category_type（bag/general）", True),
            "packaging_profile_key": ask("packaging_profile_key（可为空）"),
            "estimated_head_cost": ask("estimated_head_cost", True),
            "conservative_head_cost": ask("conservative_head_cost（可为空）"),
        })
    raw["actual_head_cost"] = ask("actual_head_cost", True)
    raw["notes"] = ask("notes（可为空）")
    record = append_feedback(raw, head_estimate_path)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return record


def import_csv(input_path: Path, head_estimate_path: Path = HEAD_ESTIMATE_PATH) -> int:
    rows = read_csv(input_path)
    if not rows:
        raise ValueError("导入CSV没有数据")
    if "actual_head_cost" not in rows[0]:
        raise ValueError("导入CSV缺少字段: actual_head_cost")
    manual_required = {"product_link", "category_type", "estimated_head_cost"}
    for index, row in enumerate(rows, start=2):
        if not str(row.get("actual_head_cost") or "").strip():
            raise ValueError(f"CSV第{index}行缺少 actual_head_cost")
        if not str(row.get("estimate_id") or "").strip():
            missing = [field for field in manual_required if not str(row.get(field) or "").strip()]
            if missing:
                raise ValueError(f"CSV第{index}行无estimate_id，缺少人工录入字段: {', '.join(sorted(missing))}")
        append_feedback(row, head_estimate_path)
    return len(rows)


def apply_suggestion(
    profile_key: str | None = None,
    proposal_path: Path | None = None,
    assume_yes: bool = False,
) -> bool:
    if not profile_key or not proposal_path:
        print("新版不再按金额自动生成乘数。请由AI检查商品图后提供 --profile-key 和 --proposal。")
        return False
    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    if profile_key not in profiles:
        raise ValueError(f"未知 packaging_profile_key: {profile_key}")
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    allowed = {"profile_cn", "packaging_method", "behavior", "packing"}
    proposed = dict(profiles[profile_key])
    proposed.update({key: value for key, value in proposal.items() if key in allowed})
    validate_profile(proposed)
    print("原参数：")
    print(json.dumps(profiles[profile_key], ensure_ascii=False, indent=2))
    print("建议参数：")
    print(json.dumps(proposed, ensure_ascii=False, indent=2))
    print(MODE_NOTE)
    if not assume_yes and input("确认应用以上包装画像？Y/N: ").strip().lower() != "y":
        print("已取消。")
        return False
    profiles[profile_key] = proposed
    write_json(PROFILES_PATH, profiles)
    rows = read_feedback(FEEDBACK_PATH)
    for row in rows:
        if row.get("packaging_profile_key") == profile_key:
            row["applied_to_profile"] = "true"
    write_csv(FEEDBACK_PATH, rows, FEEDBACK_FIELDS)
    generate_accuracy_report(FEEDBACK_PATH, REPORT_PATH)
    print(f"已更新: {PROFILES_PATH}")
    return True


def update_exchange_rate(
    rate: float,
    source: str = "user_provided",
    updated_at: str | None = None,
    assume_yes: bool = False,
) -> bool:
    if rate <= 0:
        raise ValueError("rate 必须大于 0")
    update_date = updated_at or date.today().isoformat()
    datetime.strptime(update_date, "%Y-%m-%d")
    config = load_config()
    proposed = dict(config, usd_cny_rate=rate, usd_cny_rate_updated_at=update_date,
                    usd_cny_rate_source=source.strip() or "user_provided")
    print(json.dumps({"原汇率": config["usd_cny_rate"], "新汇率": rate,
                      "更新时间": update_date, "来源": proposed["usd_cny_rate_source"]},
                     ensure_ascii=False, indent=2))
    if not assume_yes and input("确认更新汇率？Y/N: ").strip().lower() != "y":
        print("已取消。")
        return False
    write_json(DEFAULT_CONFIG_PATH, proposed)
    print(f"已更新: {DEFAULT_CONFIG_PATH}")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="头程金额反推与包装判断纠错")
    commands = parser.add_subparsers(dest="command", required=True)
    adder = commands.add_parser("add", help="逐条录入实际头程金额")
    adder.add_argument("--estimate-id")
    adder.add_argument("--actual-head-cost", type=float)
    adder.add_argument("--notes", default="")
    adder.add_argument("--record-path", type=Path, default=HEAD_ESTIMATE_PATH)
    importer = commands.add_parser("import", help="批量导入CSV")
    importer.add_argument("--file", required=True, type=Path)
    importer.add_argument("--record-path", type=Path, default=HEAD_ESTIMATE_PATH)
    commands.add_parser("report", help="重新生成误差报告")
    commands.add_parser("rebuild-diagnoses", help="重新判断历史误差原因")
    apply = commands.add_parser("apply-suggestion", help="人工确认复核后提出的包装画像参数")
    apply.add_argument("--profile-key")
    apply.add_argument("--proposal", type=Path)
    apply.add_argument("--yes", action="store_true")
    rate = commands.add_parser("set-rate", help="手工更新汇率")
    rate.add_argument("--rate", required=True, type=float)
    rate.add_argument("--source", default="user_provided")
    rate.add_argument("--date")
    rate.add_argument("--yes", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_storage()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "add":
            if args.estimate_id is not None or args.actual_head_cost is not None:
                if not args.estimate_id or args.actual_head_cost is None:
                    raise ValueError("非交互录入必须同时提供 --estimate-id 和 --actual-head-cost")
                record = append_feedback({"estimate_id": args.estimate_id, "actual_head_cost": args.actual_head_cost, "notes": args.notes}, args.record_path)
                print(json.dumps(record, ensure_ascii=False, indent=2))
            else:
                add_interactive(args.record_path)
        elif args.command == "import":
            print(f"成功导入 {import_csv(args.file, args.record_path)} 条反馈。")
        elif args.command == "report":
            print(f"已生成 {len(generate_accuracy_report(FEEDBACK_PATH, REPORT_PATH))} 个分组。")
        elif args.command == "rebuild-diagnoses":
            rebuild_diagnoses(FEEDBACK_PATH, ESTIMATE_PATH)
            generate_accuracy_report(FEEDBACK_PATH, REPORT_PATH)
            print("已重新判断历史误差原因。")
        elif args.command == "apply-suggestion":
            apply_suggestion(args.profile_key, args.proposal, args.yes)
        elif args.command == "set-rate":
            update_exchange_rate(args.rate, args.source, args.date, args.yes)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
