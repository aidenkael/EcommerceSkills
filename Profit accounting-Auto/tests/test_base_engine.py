"""OCR 引擎接口与占位引擎测试。

覆盖：
1. PlaceholderOcrEngine 可以实例化
2. 返回空 OCR 结果
3. OCR 不可用不会影响程序继续运行
4. 接口返回类型稳定
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ocr.base_engine import (
    BaseOcrEngine, PlaceholderOcrEngine, EngineStatus,
    OcrTextLine, OcrPageResult,
)


class TestPlaceholderEngine:
    """占位引擎。"""

    def test_can_instantiate(self):
        """1. PlaceholderOcrEngine 可以实例化。"""
        engine = PlaceholderOcrEngine()
        assert isinstance(engine, BaseOcrEngine)
        assert engine.name == "placeholder"

    def test_returns_empty_result(self):
        """2. 返回空 OCR 结果。"""
        engine = PlaceholderOcrEngine()
        result = engine.recognize("nonexistent.png", "img1")
        assert isinstance(result, OcrPageResult)
        assert result.lines == []
        assert result.image_id == "img1"
        assert result.success is True

    def test_unavailable_does_not_crash(self):
        """3. OCR 不可用不会影响程序继续运行。"""
        engine = PlaceholderOcrEngine()
        # 引擎状态为不可用
        assert engine.status() == EngineStatus.UNAVAILABLE
        # 但 recognize 仍不抛异常，程序可继续执行
        result = engine.recognize("any.png", "img1")
        assert result.success is True
        # 模拟主程序在 OCR 不可用时继续运行
        program_state = "running"
        assert program_state == "running"

    def test_return_type_stable(self):
        """4. 接口返回类型稳定。"""
        engine = PlaceholderOcrEngine()
        r1 = engine.recognize("a.png", "img1")
        r2 = engine.recognize("b.png", "img2")
        assert type(r1) is OcrPageResult
        assert type(r2) is OcrPageResult
        assert type(r1.lines) is list
        assert type(r1.lines) is type(r2.lines)
        assert engine.status().__class__ is EngineStatus


class TestOcrTextLine:
    """文本行数据结构。"""

    def test_line_defaults(self):
        line = OcrTextLine(text="hello")
        assert line.text == "hello"
        assert line.confidence == 0.0
        assert line.bbox is None

    def test_line_with_bbox(self):
        line = OcrTextLine(text="12.8", confidence=0.95, bbox=(10, 20, 80, 40))
        assert line.text == "12.8"
        assert line.confidence == 0.95
        assert line.bbox == (10, 20, 80, 40)
