from __future__ import annotations

import argparse
import csv
import json
import sys
import unittest
from pathlib import Path
from typing import Any

from .api import serve
from .service import EstimatorService
from .utils import load_jsonl
from .vision import AgentRequiredError


ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def images_in(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
        return [path]
    if not path.exists():
        return []
    return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def write_agent_template(input_path: Path, output_path: Path) -> int:
    imgs = images_in(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        for img in imgs:
            item = {
                "image_path": rel(img),
                "product_name": "",
                "category": "",
                "keywords": [],
                "rigidity": "unknown",
                "package_type": "未知",
                "quantity": 1,
                "actual_weight_kg": None,
                "dimensions_cm": None,
                "packed_weight_kg": None,
                "packed_dimensions_cm": None,
                "compressible": False,
                "fragile": False,
                "confidence": "low",
                "evidence": "",
                "notes": "由 Agent 看图后填写；不能确认的重量和尺寸保持 null。",
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(imgs)


def write_results(results: list[dict[str, Any]], jsonl_path: Path, csv_path: Path) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8", newline="") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    columns = [
        "image_path", "product_name", "chargeable_weight_kg", "weight_low_kg", "weight_high_kg",
        "深圳货代_rmb", "义乌货代_rmb", "recommended_provider", "recommended_cost_rmb",
        "recommended_low_rmb", "recommended_high_rmb", "needs_review", "review_reasons",
        "top_similarity", "neighbors",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in results:
            wr = r.get("chargeable_weight_range_kg") or [None, None]
            cr = r.get("recommended_cost_range_rmb") or [None, None]
            cal = r.get("calibration") or {}
            row = {
                "image_path": r.get("image_path"),
                "product_name": r.get("product_name"),
                "chargeable_weight_kg": r.get("chargeable_weight_kg"),
                "weight_low_kg": wr[0],
                "weight_high_kg": wr[1],
                "深圳货代_rmb": (r.get("provider_costs") or {}).get("深圳货代", {}).get("estimated_cost_rmb"),
                "义乌货代_rmb": (r.get("provider_costs") or {}).get("义乌货代", {}).get("estimated_cost_rmb"),
                "recommended_provider": r.get("recommended_provider"),
                "recommended_cost_rmb": r.get("recommended_cost_rmb"),
                "recommended_low_rmb": cr[0],
                "recommended_high_rmb": cr[1],
                "needs_review": r.get("needs_review"),
                "review_reasons": "；".join(r.get("review_reasons") or []),
                "top_similarity": cal.get("top_similarity"),
                "neighbors": " | ".join(f"#{n.get('id')} {n.get('product_label')}" for n in cal.get("neighbors", [])),
            }
            writer.writerow(row)


def cmd_template(args: argparse.Namespace) -> int:
    count = write_agent_template(Path(args.input), Path(args.output))
    print(f"已为 {count} 张图片生成 Agent 分析模板: {args.output}")
    if count == 0:
        print("请先把商品图片放入 input_images 文件夹。")
    return 0


def cmd_estimate_agent(args: argparse.Namespace) -> int:
    service = EstimatorService(ROOT)
    items = load_jsonl(Path(args.analysis))
    results = [service.estimate_analysis(item, tail_cost_rmb=args.tail_cost) for item in items]
    write_results(results, Path(args.output_jsonl), Path(args.output_csv))
    print(f"已完成 {len(results)} 条核算。")
    print(f"JSONL: {args.output_jsonl}")
    print(f"CSV:   {args.output_csv}")
    return 0


def cmd_estimate_images(args: argparse.Namespace) -> int:
    service = EstimatorService(ROOT)
    imgs = images_in(Path(args.input))
    if not imgs:
        print("input_images 中没有图片。")
        return 0
    results: list[dict[str, Any]] = []
    try:
        for idx, img in enumerate(imgs, start=1):
            print(f"[{idx}/{len(imgs)}] 分析 {img.name}")
            results.append(service.estimate_image(img, provider=args.provider))
    except AgentRequiredError as exc:
        template = Path("work/agent_analysis.jsonl")
        count = write_agent_template(Path(args.input), template)
        print(str(exc))
        print(f"已生成 {count} 条模板: {template}")
        print("在 Agent 中打开本目录并说：读取 AGENTS.md，分析 input_images 后完成物流核算。")
        return 0
    write_results(results, Path(args.output_jsonl), Path(args.output_csv))
    print(f"已完成 {len(results)} 条核算。输出位于 output 文件夹。")
    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    service = EstimatorService(ROOT)
    feedback: dict[str, Any] = {
        "image_path": args.image,
        "actual_allocated_head_cost_rmb": args.actual_cost,
        "actual_weight_kg": args.actual_weight,
        "dimensions_cm": [float(x) for x in args.dimensions.split(",")] if args.dimensions else None,
        "product_name": args.product_name or "",
        "notes": args.notes or "",
        "estimated_head_cost_rmb_at_time": args.estimated_cost,
    }
    service.add_feedback(feedback)
    print("反馈已追加到 data/feedback.jsonl。重新运行后会自动读取。")
    return 0


def cmd_self_check(_: argparse.Namespace) -> int:
    print(f"项目根目录: {ROOT}")
    service = EstimatorService(ROOT)
    print(f"校准记录: {len(service.calibration.records)}")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="基于图片与历史校准数据的头程物流核算工具")
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("agent-template", help="为 Agent 生成待填写的图片分析 JSONL")
    t.add_argument("--input", default="input_images")
    t.add_argument("--output", default="work/agent_analysis.jsonl")
    t.set_defaults(func=cmd_template)

    a = sub.add_parser("estimate-agent", help="读取 Agent 完成的分析 JSONL 并计算")
    a.add_argument("--analysis", default="work/agent_analysis.jsonl")
    a.add_argument("--output-jsonl", default="output/estimates.jsonl")
    a.add_argument("--output-csv", default="output/estimates.csv")
    a.add_argument("--tail-cost", type=float, default=None, help="可选：显式传入尾程费用")
    a.set_defaults(func=cmd_estimate_agent)

    i = sub.add_parser("estimate-images", help="使用视觉 API 或本地 Ollama 直接处理图片")
    i.add_argument("--input", default="input_images")
    i.add_argument("--provider", default="auto", choices=["auto", "agent", "openai_compatible", "ollama"])
    i.add_argument("--output-jsonl", default="output/estimates.jsonl")
    i.add_argument("--output-csv", default="output/estimates.csv")
    i.set_defaults(func=cmd_estimate_images)

    f = sub.add_parser("add-feedback", help="追加真实反馈，供以后校准")
    f.add_argument("--image", required=True)
    f.add_argument("--actual-cost", type=float, required=True)
    f.add_argument("--actual-weight", type=float, default=None)
    f.add_argument("--estimated-cost", type=float, default=None, help="可选：该次预测值，用于计算误差修正比例")
    f.add_argument("--dimensions", default=None, help="长,宽,高，例如 12,8,3")
    f.add_argument("--product-name", default="")
    f.add_argument("--notes", default="")
    f.set_defaults(func=cmd_feedback)

    s = sub.add_parser("serve", help="启动本地 HTTP API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(func=lambda args: (serve(ROOT, args.host, args.port), 0)[1])

    c = sub.add_parser("self-check", help="运行结构和规则自检")
    c.set_defaults(func=cmd_self_check)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
