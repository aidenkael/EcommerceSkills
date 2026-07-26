"""可替换的 OCR 引擎接口。

本步骤只定义接口和占位实现，不接入真实 OCR。

禁止事项（本步骤）：
- import paddleocr / paddlepaddle / cv2
- 下载模型
- 联网
- 接入真实 OCR

占位引擎返回空结果但不抛致命异常，保证主窗口能正常启动。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class EngineStatus(Enum):
    """引擎可用状态。"""
    READY = "ready"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class OcrTextLine:
    """单行 OCR 文本结果。"""
    text: str
    confidence: float = 0.0
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x1, y1, x2, y2)，调试用


@dataclass
class OcrPageResult:
    """单张图片的 OCR 结果。"""
    image_id: str
    lines: list = field(default_factory=list)  # list[OcrTextLine]
    success: bool = True
    error: Optional[str] = None


class BaseOcrEngine(ABC):
    """OCR 引擎统一接口。

    字段提取器只依赖此接口，未来换引擎不改提取器和利润计算。
    """

    @property
    def name(self) -> str:
        """引擎名称，用于 IntakeSession.engine_name。"""
        return "base"

    @abstractmethod
    def status(self) -> EngineStatus:
        """返回引擎当前可用状态。"""

    @abstractmethod
    def recognize(self, image_path: str, image_id: str) -> OcrPageResult:
        """识别单张图片，返回文本行列表。

        失败时返回 success=False 的 OcrPageResult，不抛致命异常。
        """


class PlaceholderOcrEngine(BaseOcrEngine):
    """占位引擎：永远返回空结果，status=UNAVAILABLE，但不抛异常。

    用途：
    - 开发期未接入真实 OCR 时跑通流程；
    - 真实引擎初始化失败时降级，保证主窗口能启动、手动核算不受影响。
    """

    @property
    def name(self) -> str:
        return "placeholder"

    def status(self) -> EngineStatus:
        return EngineStatus.UNAVAILABLE

    def recognize(self, image_path: str, image_id: str) -> OcrPageResult:
        # 不读取图片、不联网，直接返回空结果
        return OcrPageResult(image_id=image_id, lines=[], success=True, error=None)
