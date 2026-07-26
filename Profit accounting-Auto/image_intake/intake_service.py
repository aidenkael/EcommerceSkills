"""OCR 图片录入会话与文件管理。

本步骤只实现：
- 会话目录创建（默认 LOCALAPPDATA，支持注入）
- 图片副本管理（shutil.copy2 + UUID 重命名，不移动/覆盖/删除源文件）
- session.json 原子读写（UTF-8、ensure_ascii=False、os.replace）
- 调用 PlaceholderOcrEngine（返回空结果，不生成虚假候选）
- 旧会话清理（只删 session_root 直属目录，不跟随符号链接）

不实现：字段提取、GUI、真实 OCR、OpenCV 预处理。
"""
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from image_intake.image_types import ImageType
from image_intake.result_models import (
    OcrCandidate, FieldCandidates, FieldSelection, IntakeSession, MeasurementScope,
)
from ocr.base_engine import BaseOcrEngine, OcrPageResult, PlaceholderOcrEngine


FORMAT_VERSION = 1
ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


def resolve_default_session_root() -> Path:
    """默认会话根目录。

    优先读取环境变量 LOCALAPPDATA；缺失时回退到 Path.home()/AppData/Local。
    只返回路径，不创建目录。
    """
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "ProfitAccountingAuto" / "ocr_sessions"
    return Path.home() / "AppData" / "Local" / "ProfitAccountingAuto" / "ocr_sessions"


def _looks_like_path(raw: str) -> bool:
    """判断字符串是否像路径而非 session_id。"""
    if not raw:
        return False
    # Unix 绝对路径
    if raw.startswith("/"):
        return True
    # Windows 盘符绝对路径，如 C:\\...
    if len(raw) > 1 and raw[1] == ":":
        return True
    # 含路径分隔符
    return ("/" in raw) or ("\\" in raw) or (os.sep in raw and os.sep != "/")


class IntakeService:
    """OCR 录入会话服务。

    默认会话根目录为 %LOCALAPPDATA%\\ProfitAccountingAuto\\ocr_sessions\\。
    测试时应注入 tmp_path，避免写入真实 LOCALAPPDATA。
    """

    def __init__(self, session_root: Optional[Union[str, Path]] = None,
                 engine: Optional[BaseOcrEngine] = None):
        self._root = Path(session_root) if session_root is not None else resolve_default_session_root()
        self._engine = engine if engine is not None else PlaceholderOcrEngine()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def session_root(self) -> Path:
        return self._root

    @property
    def engine(self) -> BaseOcrEngine:
        return self._engine

    # ─── 会话创建 ──────────────────────────────────────────

    def create_session(self) -> IntakeSession:
        """创建一个新录入会话，生成目录结构和空 session.json。"""
        now = datetime.now()
        session_id = now.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        self._validate_session_id(session_id)
        session_dir = self._root / session_id
        (session_dir / "original").mkdir(parents=True, exist_ok=True)
        (session_dir / "preprocessed").mkdir(parents=True, exist_ok=True)
        (session_dir / "ocr_raw").mkdir(parents=True, exist_ok=True)
        session = IntakeSession(
            session_id=session_id,
            created_at=now.isoformat(timespec="seconds"),
            session_dir=str(session_dir),
            engine_name=self._engine.name,
        )
        # 创建后立即写一份空 session.json，便于后续 load
        self.save_session(session)
        return session

    # ─── 图片管理 ──────────────────────────────────────────

    def add_image(self, session: IntakeSession, source_path: Union[str, Path],
                  image_type: ImageType) -> dict:
        """复制源图片到会话 original 目录，返回图片记录。

        - 源文件必须存在且是普通文件；
        - image_type 必须是 ImageType 枚举；
        - 扩展名必须是允许的 5 种之一；
        - 使用 shutil.copy2 复制，不移动/覆盖/删除源文件；
        - 保存名统一为 <image_id><扩展名小写>，避免同名冲突。
        """
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(f"源文件不存在或不是普通文件: {source}")
        if not isinstance(image_type, ImageType):
            raise ValueError(f"非法 image_type: {image_type!r}，必须是 ImageType 枚举")
        ext = source.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的扩展名: {ext}，允许: {sorted(ALLOWED_EXTENSIONS)}")

        image_id = uuid.uuid4().hex
        stored_filename = f"{image_id}{ext}"
        session_dir = Path(session.session_dir)
        original_dir = session_dir / "original"
        original_dir.mkdir(parents=True, exist_ok=True)
        stored_path = original_dir / stored_filename
        shutil.copy2(source, stored_path)

        record = {
            "image_id": image_id,
            "original_filename": source.name,
            "stored_filename": stored_filename,
            "stored_path": str(stored_path),
            "image_type": image_type.value,
            "added_at": datetime.now().isoformat(timespec="seconds"),
        }
        session.images.append(record)
        return record

    def add_image_bytes(self, session: IntakeSession, data: bytes,
                        original_filename: str, image_type) -> dict:
        """将图片字节数据保存到会话 original 目录。

        - data: 图片字节内容（PNG/JPEG等）；
        - original_filename: 显示用的原始文件名（如 clipboard_20260727_120000.png）；
        - image_type: ImageType 枚举；
        - 返回 image_record，与 add_image 格式一致。
        """
        if not isinstance(image_type, ImageType):
            raise ValueError(f"非法 image_type: {image_type!r}，必须是 ImageType 枚举")
        if not isinstance(data, bytes) or len(data) == 0:
            raise ValueError("数据不能为空")
        # 使用 .png 作为默认存储扩展名
        ext = ".png"
        image_id = uuid.uuid4().hex
        stored_filename = f"{image_id}{ext}"
        session_dir = Path(session.session_dir)
        original_dir = session_dir / "original"
        original_dir.mkdir(parents=True, exist_ok=True)
        stored_path = original_dir / stored_filename
        with open(stored_path, "wb") as f:
            f.write(data)
        record = {
            "image_id": image_id,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "stored_path": str(stored_path),
            "image_type": image_type.value,
            "added_at": datetime.now().isoformat(timespec="seconds"),
            "source": "clipboard",
        }
        session.images.append(record)
        return record

    # ─── session.json 读写 ──────────────────────────────────

    def save_session(self, session: IntakeSession) -> Path:
        """原子写入 session.json（临时文件 + os.replace）。"""
        session_dir = Path(session.session_dir)
        self._validate_path_in_root(session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_json_path = session_dir / "session.json"
        tmp_path = session_dir / "session.json.tmp"
        data = self._session_to_dict(session)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, session_json_path)
        return session_json_path

    def load_session(self, session_id_or_path: Union[str, Path]) -> IntakeSession:
        """从 session_id 或会话目录路径读取 session.json 并恢复 IntakeSession。"""
        raw = str(session_id_or_path)
        if _looks_like_path(raw):
            session_dir = Path(raw)
            self._validate_path_in_root(session_dir)
        else:
            self._validate_session_id(raw)
            session_dir = self._root / raw

        session_json_path = session_dir / "session.json"
        if not session_json_path.is_file():
            raise FileNotFoundError(f"session.json 不存在: {session_json_path}")

        try:
            with open(session_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"session.json 损坏，无法解析: {exc}") from exc

        fv = data.get("format_version")
        if fv != FORMAT_VERSION:
            raise ValueError(f"不支持的 format_version: {fv!r}，当前支持: {FORMAT_VERSION}")
        return self._session_from_dict(data, session_dir)

    # ─── OCR 处理 ──────────────────────────────────────────

    def process_image(self, session: IntakeSession, image_id: str) -> OcrPageResult:
        """调用引擎识别单张图片。本步骤用 PlaceholderOcrEngine 返回空结果。"""
        record = next((img for img in session.images if img["image_id"] == image_id), None)
        if record is None:
            raise ValueError(f"image_id 不存在于当前会话: {image_id}")
        # 引擎不可用时不抛致命异常，返回空结果
        return self._engine.recognize(record["stored_path"], image_id)

    # ─── 清理 ──────────────────────────────────────────────

    def cleanup_sessions_older_than(self, days: int,
                                    now: Optional[datetime] = None) -> list:
        """清理超过 days 天的会话目录，返回被删除的 session_id 列表。

        - days 必须是非负整数；
        - 只清理 session_root 直属目录；
        - 不跟随符号链接；
        - 不删除 session_root 之外的路径；
        - 本阶段不自动调用。
        """
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            raise ValueError(f"days 必须是非负整数: {days!r}")
        if now is None:
            now = datetime.now()
        deleted = []
        if not self._root.is_dir():
            return deleted
        root_resolved = self._root.resolve()
        for entry in self._root.iterdir():
            # 跳过符号链接和非目录
            if entry.is_symlink() or not entry.is_dir():
                continue
            # 验证解析后仍在 root 内，防止符号链接逃逸
            try:
                entry.resolve().relative_to(root_resolved)
            except ValueError:
                continue
            # 用 session.json 的修改时间判断，没有则用目录修改时间
            session_json = entry / "session.json"
            if session_json.is_file():
                mtime = datetime.fromtimestamp(session_json.stat().st_mtime)
            else:
                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
            age_days = (now - mtime).total_seconds() / 86400.0
            if age_days > days:
                shutil.rmtree(entry)
                deleted.append(entry.name)
        return deleted

    # ─── 路径安全 ──────────────────────────────────────────

    def _validate_session_id(self, session_id: str) -> None:
        """防止通过 session_id 中的 .. 或分隔符穿越到 session_root 之外。"""
        if not session_id:
            raise ValueError("session_id 不能为空")
        if ".." in session_id:
            raise ValueError(f"非法 session_id（含 ..）: {session_id!r}")
        if ("/" in session_id) or ("\\" in session_id) or (os.sep in session_id and os.sep not in ("/", "\\")):
            raise ValueError(f"非法 session_id（含路径分隔符）: {session_id!r}")
        # 二次验证：解析后必须在 root 内
        target = (self._root / session_id).resolve()
        root_resolved = self._root.resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            raise ValueError(f"session_id 越界: {session_id!r}")

    def _validate_path_in_root(self, path: Path) -> None:
        """验证给定路径解析后仍在 session_root 内。"""
        root_resolved = self._root.resolve()
        target = Path(path).resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            raise ValueError(f"路径越界，不在 session_root 内: {path}")

    # ─── 序列化（service 层职责，不污染 result_models） ─────

    def _session_to_dict(self, session: IntakeSession) -> dict:
        return {
            "format_version": FORMAT_VERSION,
            "session_id": session.session_id,
            "created_at": session.created_at,
            "engine_name": session.engine_name,
            "images": list(session.images),
            "field_candidates": {
                name: self._field_candidates_to_dict(fc)
                for name, fc in session.field_candidates.items()
            },
            "selections": {
                name: self._selection_to_dict(sel)
                for name, sel in session.selections.items()
            },
        }

    def _field_candidates_to_dict(self, fc: FieldCandidates) -> dict:
        return {
            "field_name": fc.field_name,
            "candidates": [self._candidate_to_dict(c) for c in fc.candidates],
            "selected_candidate_id": fc.selected_candidate_id,
        }

    def _candidate_to_dict(self, c: OcrCandidate) -> dict:
        return {
            "candidate_id": c.candidate_id,
            "field_name": c.field_name,
            "parsed_value": c.parsed_value,
            "normalized_value": c.normalized_value,
            "unit_original": c.unit_original,
            "unit_normalized": c.unit_normalized,
            "selectable": c.selectable,
            "source_image": c.source_image,
            "raw_text": c.raw_text,
            "confidence": c.confidence,
            "measurement_group_id": c.measurement_group_id,
        }

    def _selection_to_dict(self, sel: FieldSelection) -> dict:
        return {
            "field_name": sel.field_name,
            "source_candidate_id": sel.source_candidate_id,
            "confirmed_value": sel.confirmed_value,
            "confirmed_unit": sel.confirmed_unit,
            "measurement_scope": sel.measurement_scope.value,
            "user_modified": sel.user_modified,
        }

    def _session_from_dict(self, data: dict, session_dir: Path) -> IntakeSession:
        session = IntakeSession(
            session_id=data["session_id"],
            created_at=data["created_at"],
            session_dir=str(session_dir),
            engine_name=data.get("engine_name", "placeholder"),
            images=list(data.get("images", [])),
            field_candidates={},
            selections={},
        )
        for name, fc_data in data.get("field_candidates", {}).items():
            session.field_candidates[name] = self._field_candidates_from_dict(fc_data)
        for name, sel_data in data.get("selections", {}).items():
            session.selections[name] = self._selection_from_dict(sel_data)
        return session

    def _field_candidates_from_dict(self, data: dict) -> FieldCandidates:
        return FieldCandidates(
            field_name=data["field_name"],
            candidates=[self._candidate_from_dict(c) for c in data.get("candidates", [])],
            selected_candidate_id=data.get("selected_candidate_id"),
        )

    def _candidate_from_dict(self, data: dict) -> OcrCandidate:
        return OcrCandidate(
            field_name=data["field_name"],
            parsed_value=data.get("parsed_value"),
            source_image=data["source_image"],
            raw_text=data["raw_text"],
            confidence=data.get("confidence", 0.0),
            normalized_value=data.get("normalized_value"),
            unit_original=data.get("unit_original"),
            unit_normalized=data.get("unit_normalized"),
            selectable=data.get("selectable", False),
            measurement_group_id=data.get("measurement_group_id"),
            candidate_id=data.get("candidate_id") or uuid.uuid4().hex,
        )

    def _selection_from_dict(self, data: dict) -> FieldSelection:
        return FieldSelection(
            field_name=data["field_name"],
            source_candidate_id=data["source_candidate_id"],
            confirmed_value=data.get("confirmed_value"),
            confirmed_unit=data.get("confirmed_unit"),
            measurement_scope=MeasurementScope(data["measurement_scope"]),
            user_modified=data.get("user_modified", False),
        )
