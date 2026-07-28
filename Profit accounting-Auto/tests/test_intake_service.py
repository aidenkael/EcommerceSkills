"""OCR 图片录入会话与文件管理测试。

覆盖 20 项：
1. 注入 tmp_path 后创建完整会话目录
2. session_id 格式正确且连续创建不重复
3. 默认目录解析到 LOCALAPPDATA
4. LOCALAPPDATA 缺失时回退路径正确
5. 添加图片后源文件仍存在且内容未改变
6. 两个同名图片保存后不会冲突
7. 文件扩展名统一为小写
8. 不支持的扩展名被拒绝
9. 不存在的源文件被拒绝
10. 非法 image_type 被拒绝
11. session.json 使用 UTF-8 并保留中文文件名
12. session 保存后能够完整读取
13. OCR 候选和 FieldSelection 保存、读取后不丢字段
14. format_version 不支持时明确失败
15. 损坏 JSON 时明确失败
16. PlaceholderOcrEngine 处理后返回空结果且不产生候选
17. cleanup_sessions_older_than 只删除超过期限的会话
18. days 为负数时拒绝
19. 路径穿越 session_id 被拒绝
20. 测试全过程不写入真实 LOCALAPPDATA
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from image_intake.intake_service import (
    IntakeService, resolve_default_session_root, FORMAT_VERSION,
)
from image_intake.image_types import ImageType
from image_intake.result_models import (
    OcrCandidate, FieldCandidates, FieldSelection, MeasurementScope,
)
from ocr.base_engine import PlaceholderOcrEngine, OcrPageResult


def _make_image(tmp_path, name="test.png", content=b"\x89PNG fake"):
    p = tmp_path / name
    p.write_bytes(content)
    return p


class TestSessionCreation:
    """1-2. 会话创建。"""

    def test_create_session_makes_full_directory(self, tmp_path):
        """1. 注入 tmp_path 后创建完整会话目录。"""
        svc = IntakeService(session_root=tmp_path)
        session = svc.create_session()
        d = Path(session.session_dir)
        assert (d / "original").is_dir()
        assert (d / "preprocessed").is_dir()
        assert (d / "ocr_raw").is_dir()
        assert (d / "session.json").is_file()

    def test_session_id_format_and_unique(self, tmp_path):
        """2. session_id 格式正确且连续创建不重复。"""
        svc = IntakeService(session_root=tmp_path)
        ids = [svc.create_session().session_id for _ in range(3)]
        # 格式 YYYYMMDD_HHMMSS_<8hex>
        for sid in ids:
            assert re.fullmatch(r"\d{8}_\d{6}_[0-9a-f]{8}", sid), sid
        # 不重复
        assert len(set(ids)) == 3


class TestDefaultRoot:
    """3-4. 默认目录解析。"""

    def test_default_root_uses_localappdata(self, monkeypatch, tmp_path):
        """3. 默认目录解析到 LOCALAPPDATA。"""
        fake_local = tmp_path / "fakeLocal"
        monkeypatch.setenv("LOCALAPPDATA", str(fake_local))
        root = resolve_default_session_root()
        assert root == fake_local / "ProfitAccountingAuto" / "ocr_sessions"

    def test_default_root_fallback_without_localappdata(self, monkeypatch, tmp_path):
        """4. LOCALAPPDATA 缺失时回退到 home/AppData/Local。"""
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        root = resolve_default_session_root()
        assert root == Path.home() / "AppData" / "Local" / "ProfitAccountingAuto" / "ocr_sessions"


class TestAddImage:
    """5-10. 图片添加。"""

    def test_source_file_unchanged(self, tmp_path):
        """5. 添加图片后源文件仍存在且内容未改变。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        src = _make_image(tmp_path, "a.png", b"original-bytes")
        svc.add_image(session, src, ImageType.SHEIN_PRICING)
        assert src.is_file()
        assert src.read_bytes() == b"original-bytes"

    def test_two_same_name_no_conflict(self, tmp_path):
        """6. 两个同名图片保存后不会冲突。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        # 两个不同目录下的同名文件
        d1 = tmp_path / "dir1"; d1.mkdir()
        d2 = tmp_path / "dir2"; d2.mkdir()
        f1 = d1 / "x.png"; f1.write_bytes(b"aaa")
        f2 = d2 / "x.png"; f2.write_bytes(b"bbb")
        r1 = svc.add_image(session, f1, ImageType.SUPPLIER_COST_SHIPPING)
        r2 = svc.add_image(session, f2, ImageType.SUPPLIER_COST_SHIPPING)
        assert r1["stored_filename"] != r2["stored_filename"]
        assert Path(r1["stored_path"]).read_bytes() == b"aaa"
        assert Path(r2["stored_path"]).read_bytes() == b"bbb"
        assert len(session.images) == 2

    def test_extension_lowercased(self, tmp_path):
        """7. 文件扩展名统一为小写。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        src = _make_image(tmp_path, "UPPER.JPG")
        rec = svc.add_image(session, src, ImageType.PRODUCT_MAIN_IMAGE)
        assert rec["stored_filename"].endswith(".jpg")
        assert not rec["stored_filename"].endswith(".JPG")

    def test_unsupported_extension_rejected(self, tmp_path):
        """8. 不支持的扩展名被拒绝。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        src = _make_image(tmp_path, "a.gif")
        with pytest.raises(ValueError):
            svc.add_image(session, src, ImageType.SUPPLEMENTARY)

    def test_missing_source_rejected(self, tmp_path):
        """9. 不存在的源文件被拒绝。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        with pytest.raises(FileNotFoundError):
            svc.add_image(session, tmp_path / "nope.png", ImageType.SHEIN_PRICING)

    def test_invalid_image_type_rejected(self, tmp_path):
        """10. 非法 image_type 被拒绝。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        src = _make_image(tmp_path, "a.png")
        with pytest.raises(ValueError):
            svc.add_image(session, src, "shein_pricing")  # 字符串而非枚举


class TestSessionJson:
    """11-15. session.json 读写。"""

    def test_utf8_and_chinese_filename(self, tmp_path):
        """11. session.json 使用 UTF-8 并保留中文文件名。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        src = _make_image(tmp_path, "商品核价图.png")
        svc.add_image(session, src, ImageType.SHEIN_PRICING)
        svc.save_session(session)
        json_path = Path(session.session_dir) / "session.json"
        raw = json_path.read_bytes()
        # UTF-8 能解码，且中文不转义
        text = raw.decode("utf-8")
        assert "商品核价图.png" in text
        # 确保没有 \u 转义中文
        assert "\\u" not in text

    def test_save_then_load_complete(self, tmp_path):
        """12. session 保存后能够完整读取。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        src = _make_image(tmp_path, "a.png")
        svc.add_image(session, src, ImageType.DIMENSIONS_WEIGHT)
        # add_image 只改内存，需 save 后 load 才能读回
        svc.save_session(session)
        loaded = svc.load_session(session.session_id)
        assert loaded.session_id == session.session_id
        assert loaded.engine_name == session.engine_name
        assert len(loaded.images) == 1
        assert loaded.images[0]["original_filename"] == "a.png"
        assert loaded.images[0]["image_type"] == "dimensions_weight"

    def test_candidates_and_selections_roundtrip(self, tmp_path):
        """13. OCR 候选和 FieldSelection 保存、读取后不丢字段。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        # 构造候选
        c = OcrCandidate(
            field_name="weight_g", parsed_value=0.5, source_image="img1",
            raw_text="0.5kg", confidence=0.92,
            normalized_value=500.0, unit_original="kg", unit_normalized="g",
            selectable=True, measurement_group_id="grp1",
        )
        fc = FieldCandidates(field_name="weight_g", candidates=[c], selected_candidate_id=c.candidate_id)
        session.field_candidates["weight_g"] = fc
        # 构造选择
        sel = FieldSelection(
            field_name="weight_g", source_candidate_id=c.candidate_id,
            confirmed_value=500.0, confirmed_unit="g",
            measurement_scope=MeasurementScope.BARE, user_modified=False,
        )
        session.selections["weight_g"] = sel
        svc.save_session(session)
        loaded = svc.load_session(session.session_id)
        # 候选不丢字段
        lc = loaded.field_candidates["weight_g"].candidates[0]
        assert lc.candidate_id == c.candidate_id
        assert lc.parsed_value == 0.5
        assert lc.normalized_value == 500.0
        assert lc.unit_original == "kg"
        assert lc.unit_normalized == "g"
        assert lc.selectable is True
        assert lc.measurement_group_id == "grp1"
        assert lc.raw_text == "0.5kg"
        assert lc.confidence == 0.92
        assert loaded.field_candidates["weight_g"].selected_candidate_id == c.candidate_id
        # 选择不丢字段
        ls = loaded.selections["weight_g"]
        assert ls.confirmed_value == 500.0
        assert ls.confirmed_unit == "g"
        assert ls.measurement_scope == MeasurementScope.BARE
        assert ls.user_modified is False
        assert ls.source_candidate_id == c.candidate_id

    def test_unsupported_format_version_fails(self, tmp_path):
        """14. format_version 不支持时明确失败。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        json_path = Path(session.session_dir) / "session.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["format_version"] = 999
        json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError, match="format_version"):
            svc.load_session(session.session_id)

    def test_corrupt_json_fails(self, tmp_path):
        """15. 损坏 JSON 时明确失败。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        json_path = Path(session.session_dir) / "session.json"
        json_path.write_text("{ this is not valid json }}}", encoding="utf-8")
        with pytest.raises(ValueError, match="损坏"):
            svc.load_session(session.session_id)


class TestProcessImage:
    """16. 占位引擎处理。"""

    def test_placeholder_returns_empty_no_candidates(self, tmp_path):
        """16. PlaceholderOcrEngine 处理后返回空结果且不产生候选。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        session = svc.create_session()
        src = _make_image(tmp_path, "a.png")
        rec = svc.add_image(session, src, ImageType.SHEIN_PRICING)
        result = svc.process_image(session, rec["image_id"])
        assert isinstance(result, OcrPageResult)
        assert result.lines == []
        # 不产生候选
        assert session.field_candidates == {}
        assert session.selections == {}


class TestCleanup:
    """17-18. 清理。"""

    def test_cleanup_only_old_sessions(self, tmp_path):
        """17. cleanup_sessions_older_than 只删除超过期限的会话。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        old = svc.create_session()
        new = svc.create_session()
        # 把 old 的 session.json 时间设为 10 天前
        old_json = Path(old.session_dir) / "session.json"
        old_time = time.time() - 10 * 86400
        os.utime(old_json, (old_time, old_time))
        # now 设为当前，days=5：old age=10 > 5 删，new age<5 保留
        deleted = svc.cleanup_sessions_older_than(5, now=datetime.now())
        assert old.session_id in deleted
        assert new.session_id not in deleted
        assert not Path(old.session_dir).exists()
        assert Path(new.session_dir).exists()

    def test_cleanup_rejects_negative_days(self, tmp_path):
        """18. days 为负数时拒绝。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        with pytest.raises(ValueError):
            svc.cleanup_sessions_older_than(-1)
        with pytest.raises(ValueError):
            svc.cleanup_sessions_older_than(-3.5)


class TestPathSafety:
    """19. 路径穿越防护。"""

    def test_traversal_session_id_rejected(self, tmp_path):
        """19. 路径穿越 session_id 被拒绝。"""
        svc = IntakeService(session_root=tmp_path / "sessions")
        svc.create_session()  # 至少建一个，确保 root 存在
        for evil in ("..", "../evil", "foo/bar", "foo\\bar", "..\\..\\etc"):
            with pytest.raises(ValueError):
                svc.load_session(evil)


class TestNoRealLocalAppData:
    """20. 不写真实 LOCALAPPDATA。"""

    def test_injected_root_used_not_default(self, tmp_path, monkeypatch):
        """20. 注入 tmp_path 后服务用 tmp_path，不写真实 LOCALAPPDATA。"""
        # 故意把 LOCALAPPDATA 指向 tmp 下假目录，证明服务不会越过注入值去写默认目录
        fake_default = tmp_path / "should_not_be_used"
        monkeypatch.setenv("LOCALAPPDATA", str(fake_default))
        svc = IntakeService(session_root=tmp_path / "injected")
        assert svc.session_root == tmp_path / "injected"
        session = svc.create_session()
        assert str(tmp_path / "injected") in session.session_dir
        # 默认目录没有被创建（resolve_default_session_root 不创建目录，IntakeService 也不该去建）
        assert not fake_default.exists()
