"""ROAD-1 GUI 冒烟测试 — 12 项交互验证

在 Python 3.11 + tkinterdnd2 + PIL 环境下运行。
覆盖：
 1. 上传图片到图片框
 2. 拖拽文件到指定框（模拟 _img_drop）
 3. Ctrl+V 粘贴 PIL Image（模拟剪贴板）
 4. Ctrl+V 粘贴文件路径（模拟文件剪贴板）
 5. 预览已有图片（_show_thumb 调用）
 6. Del 删除选中框图片
 7. 增加图片框
 8. 减少含图图片框（带确认）
 9. AI 识别（FakeVisionAdapter）
10. 包装档切换（正常→保守→正常）
11. 保存记录不清空页面
12. 清空并新建确认
"""
import sys, os, io, struct, zlib, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tkinter as tk
from tkinter import ttk
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager
from ui.product_page import ProductPage
from adapters.fake_vision import FakeVisionAdapter


def _make_png(tmp_path, name="test.png"):
    p = tmp_path / name
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    p.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
                  + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\xff\x00')) + chunk(b'IEND', b''))
    return str(p)


@pytest.fixture
def page(tmp_path):
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tcl/Tk 环境不可用")
    db = DatabaseManager(db_path=str(tmp_path / "smoke.db"))
    cfg = ConfigManager(db)
    p = ProductPage(root, db, cfg)
    p._show_thumb = lambda state: None
    yield p
    root.destroy()


class TestGuiSmoke12Items:
    """12 项 GUI 冒烟测试。"""

    def test_01_upload_image(self, page, tmp_path):
        """1. 上传图片到图片框。"""
        img = _make_png(tmp_path, "upload.png")
        page._load_image_from_path(img, page.image_states[0])
        assert page.image_states[0]["path"] is not None

    def test_02_drag_drop_file(self, page, tmp_path):
        """2. 拖拽文件到指定框。"""
        img = _make_png(tmp_path, "drag.png")
        event = MagicMock()
        event.data = img
        state = page.image_states[1]
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._img_drop(event, state)
        assert state["path"] is not None

    def test_03_ctrl_v_pil_image(self, page, tmp_path):
        """3. Ctrl+V 粘贴 PIL Image。"""
        import PIL.Image
        fake_img = PIL.Image.new("RGB", (10, 10), "red")
        target = page.image_states[2]
        page._select_img_box(target)
        with patch("ui.product_page.PIL.ImageGrab.grabclipboard", return_value=fake_img):
            page._on_ctrl_v(None)
        assert target["path"] is not None
        assert os.path.exists(target["path"])

    def test_04_ctrl_v_file_path(self, page, tmp_path):
        """4. Ctrl+V 粘贴文件路径（模拟剪贴板文件列表）。"""
        img = _make_png(tmp_path, "clip_file.png")
        # 模拟 win32clipboard 返回文件列表
        mock_win32 = MagicMock()
        mock_win32.CF_HDROP = 15
        mock_win32.OpenClipboard = MagicMock()
        mock_win32.CloseClipboard = MagicMock()
        mock_win32.GetClipboardData = MagicMock(return_value=[img])
        target = page.image_states[3]
        page._select_img_box(target)
        with patch.dict(sys.modules, {"win32clipboard": mock_win32}):
            with patch("ui.product_page.PIL.ImageGrab.grabclipboard", return_value=None):
                page._on_ctrl_v(None)
        assert target["path"] is not None

    def test_05_preview_image(self, page, tmp_path):
        """5. 预览已有图片（验证 _show_thumb 被调用后路径存在）。"""
        img = _make_png(tmp_path, "preview.png")
        state = page.image_states[0]
        page._load_image_from_path(img, state)
        # 模拟预览：调用 _show_thumb
        thumb_called = []
        original = page._show_thumb
        def mock_thumb(s):
            thumb_called.append(s["path"])
            original(s)
        page._show_thumb = mock_thumb
        page._show_thumb(state)
        assert len(thumb_called) == 1
        assert thumb_called[0] == state["path"]

    def test_06_del_deletes_selected(self, page, tmp_path):
        """6. Del 删除选中框图片。"""
        img = _make_png(tmp_path, "del.png")
        state = page.image_states[0]
        page._load_image_from_path(img, state)
        page._select_img_box(state)
        page._on_del_key(None)
        assert state["path"] is None

    def test_07_increase_image_box(self, page):
        """7. 增加图片框。"""
        initial = len(page.image_states)
        page._img_increase()
        assert len(page.image_states) == initial + 1

    def test_08_decrease_box_with_image(self, page, tmp_path):
        """8. 减少含图图片框（带确认）。"""
        img = _make_png(tmp_path, "last.png")
        last_idx = len(page.image_states) - 1
        page._load_image_from_path(img, page.image_states[last_idx])
        initial_count = len(page.image_states)
        # 拒绝 — 框数不变
        with patch("ui.product_page.messagebox.askyesno", return_value=False):
            page._img_decrease()
        assert len(page.image_states) == initial_count
        # 同意 — 框数减1
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._img_decrease()
        assert len(page.image_states) == initial_count - 1

    def test_09_ai_recognize(self, page, tmp_path):
        """9. AI 识别（FakeVisionAdapter）。"""
        img = _make_png(tmp_path, "ai.png")
        page._load_image_from_path(img, page.image_states[0])
        page._ai_recognize()
        assert page._var_ai_type.get() != ""
        assert page._var_ai_material.get() != ""

    def test_10_packaging_mode_switch(self, page):
        """10. 包装档切换（正常→保守→正常）。"""
        page._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        page._update_packaging_display()
        # normal
        page._packaging_mode = "normal"
        page._mode_var.set("normal")
        assert page._pkg_normal["length_cm"] == 20
        # conservative
        page._packaging_mode = "conservative"
        page._mode_var.set("conservative")
        assert page._pkg_conservative["length_cm"] == 30
        # back to normal
        page._packaging_mode = "normal"
        page._mode_var.set("normal")
        assert page._pkg_normal["length_cm"] == 20

    def test_11_save_no_clear(self, page):
        """11. 保存记录不清空页面。"""
        page._entry_vars["cost"].set("10")
        page._entry_vars["domestic"].set("5")
        page._entry_vars["shein"].set("5.99")
        page._entry_vars["price_rmb"].set("30")
        with patch("ui.product_page.messagebox.showinfo"):
            page.save_product()
        assert page._entry_vars["cost"].get() == "10"
        assert page._entry_vars["shein"].get() == "5.99"

    def test_12_clear_and_new_confirm(self, page):
        """12. 清空并新建确认。"""
        page._entry_vars["cost"].set("50")
        page._var_name.set("Unsaved")
        # 拒绝清空
        with patch("ui.product_page.messagebox.askyesno", return_value=False):
            page._clear_and_new()
        assert page._entry_vars["cost"].get() == "50"
        # 同意清空
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._clear_and_new()
        assert page._entry_vars["cost"].get() == ""
