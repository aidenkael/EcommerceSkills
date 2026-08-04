"""输出合同守卫 — 验证 renderer 输出是否符合锁定合同。

提供 validate_rendered_output() 检查输出结构，失败抛出异常。
只负责检查，不重新格式化输出。
"""
from __future__ import annotations


class OutputContractViolation(Exception):
    """输出违反锁定合同。"""
    pass


# 通用禁止词
_FORBIDDEN = [
    "```",
    "校准说明",
    "精确校准命中",
    "案例编号",
    "关键观察",
    "小结",
    "MEMORY",
    "grep",
    "内部过程",
    "验证通过",
    "偏差",
]


def validate_rendered_output(text: str, mode: str) -> None:
    """验证 renderer 输出是否符合 OUTPUT_CONTRACT 2026-08-04-v2。

    Args:
        text: renderer 返回的 Markdown 文本
        mode: "head_only" 或 "profit"

    Raises:
        OutputContractViolation: 输出格式不符合合同
    """
    if not isinstance(text, str) or not text:
        raise OutputContractViolation("输出为空")

    # 通用禁止
    text_stripped = text.strip()
    for word in _FORBIDDEN:
        if word in text_stripped:
            raise OutputContractViolation(f"输出包含禁止内容: {word}")

    # 开头结尾禁止多余空行
    if text != text_stripped:
        raise OutputContractViolation("输出开头或结尾包含多余空行")

    lines = text.split("\n")
    num_lines = len(lines)

    if mode == "head_only":
        _validate_mode2(lines, num_lines)
    elif mode == "profit":
        _validate_mode1(lines, num_lines)
    else:
        raise OutputContractViolation(f"未知模式: {mode}")


def _validate_mode2(lines: list[str], num_lines: int) -> None:
    """模式2：商品摘要 + 空行 + 头程表(6行) + 空行 + 推算句。总计10行。"""
    if num_lines != 10:
        raise OutputContractViolation(f"模式2必须恰好10行，当前{num_lines}行")

    # 行1: 商品：
    if not lines[0].startswith("商品："):
        raise OutputContractViolation("模式2第1行必须以'商品：'开头")

    # 行2: 空行
    if lines[1] != "":
        raise OutputContractViolation("模式2第2行必须为空行")

    # 行3: 头程表头
    if not lines[2].startswith("| 方案 |"):
        raise OutputContractViolation("模式2第3行必须是头程表头")

    # 行4: 对齐行
    if not lines[3].startswith("|:---:|"):
        raise OutputContractViolation("模式2第4行必须是对齐行")

    # 行5-8: 四个固定方案行
    expected_schemes = ["义乌正常", "义乌保守", "深圳正常", "深圳保守"]
    for i, expected in enumerate(expected_schemes):
        if not lines[4 + i].startswith(f"| {expected} |"):
            raise OutputContractViolation(f"模式2第{5+i}行必须以'{expected}'开头")

    # 行9: 空行
    if lines[8] != "":
        raise OutputContractViolation("模式2头程表后必须跟空行")

    # 行10: 推算：
    if not lines[9].startswith("推算："):
        raise OutputContractViolation("模式2第10行必须以'推算：'开头")


def _validate_mode1(lines: list[str], num_lines: int) -> None:
    """模式1：摘要 + 空行 + 头程表(6行) + 空行 + 参数摘要 + 空行 + 利润表(3行) + 空行 + 推算。总计16行。"""
    if num_lines != 16:
        raise OutputContractViolation(f"模式1必须恰好16行，当前{num_lines}行")

    # 行1: 商品：
    if not lines[0].startswith("商品："):
        raise OutputContractViolation("模式1第1行必须以'商品：'开头")

    # 行2: 空行
    if lines[1] != "":
        raise OutputContractViolation("模式1第2行必须为空行")

    # 行3-8: 头程表（与模式2相同）
    if not lines[2].startswith("| 方案 |"):
        raise OutputContractViolation("模式1第3行必须是头程表头")
    if not lines[3].startswith("|:---:|"):
        raise OutputContractViolation("模式1第4行必须是对齐行")
    expected_schemes = ["义乌正常", "义乌保守", "深圳正常", "深圳保守"]
    for i, expected in enumerate(expected_schemes):
        if not lines[4 + i].startswith(f"| {expected} |"):
            raise OutputContractViolation(f"模式1第{5+i}行必须以'{expected}'开头")
    if lines[8] != "":
        raise OutputContractViolation("模式1头程表后必须跟空行")

    # 行9: 当前参数：
    if not lines[9].startswith("当前参数："):
        raise OutputContractViolation("模式1第9行必须以'当前参数：'开头")

    # 行10: 空行
    if lines[10] != "":
        raise OutputContractViolation("模式1第10行必须为空行")

    # 行11: 利润表头（动态）
    if not lines[11].startswith("| 国内成本 |"):
        raise OutputContractViolation("模式1第11行必须是利润表头")
    # 验证列数：7列
    cols = [c.strip() for c in lines[11].split("|")[1:-1]]
    if len(cols) != 7:
        raise OutputContractViolation(f"模式1利润表头必须7列，当前{len(cols)}列")

    # 行12: 对齐行
    if not lines[12].startswith("|:---:|"):
        raise OutputContractViolation("模式1第12行必须是对齐行")

    # 行13: 利润数据行（必须7列）
    if not lines[13].startswith("| "):
        raise OutputContractViolation("模式1第13行必须是利润数据行")
    data_cols = [c.strip() for c in lines[13].split("|")[1:-1]]
    if len(data_cols) != 7:
        raise OutputContractViolation(f"模式1利润数据必须7列，当前{len(data_cols)}列")

    # 行14: 空行
    if lines[14] != "":
        raise OutputContractViolation("模式1第14行必须为空行")

    # 行15: 推算：
    if not lines[15].startswith("推算："):
        raise OutputContractViolation("模式1第15行必须以'推算：'开头")
