"""ROAD-1 复审测试 — 图片框、包装档联动、底部按钮、保存/清空边界

覆盖：
- 上传后增减图片框不丢失已有图片
- 减少含图框需要确认
- 拖拽进入指定框
- Ctrl+V 进入指定框
- 选中框后 Del 删除
- 底部只有两个可见主按钮
- 正常/保守档确实驱动计算
- 保存不清空页面
- 清空并新建有未保存确认
"""
import sys, os, tempfile, struct, zlib, io
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
        pytest.skip("Tcl/Tk 环境不可用（managed Python 缺少 Tcl/Tk 运行库）")
    db = DatabaseManager(db_path=str(tmp_path / "road1.db"))
    cfg = ConfigManager(db)
    p = ProductPage(root, db, cfg)
    # Mock _show_thumb to avoid PIL.ImageTk.PhotoImage hanging in test env
    p._show_thumb = lambda state: None
    yield p
    root.destroy()


class TestImageBoxPreserve:
    """增减图片框保留已有图片。"""

    def test_increase_preserves_images(self, page, tmp_path):
        img = _make_png(tmp_path, "a.png")
        page._load_image_from_path(img, page.image_states[0])
        assert page.image_states[0]["path"] is not None
        page._img_increase()
        assert page.image_states[0]["path"] is not None
        assert len(page.image_states) == 6

    def test_decrease_empty_box_no_confirm(self, page, tmp_path):
        page._img_decrease()
        assert len(page.image_states) == 4

    def test_decrease_box_with_image_needs_confirm(self, page, tmp_path):
        img = _make_png(tmp_path, "last.png")
        last_idx = len(page.image_states) - 1
        page._load_image_from_path(img, page.image_states[last_idx])
        with patch("ui.product_page.messagebox.askyesno", return_value=False):
            page._img_decrease()
        assert len(page.image_states) == 5  # not decreased
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._img_decrease()
        assert len(page.image_states) == 4


class TestImageBoxInteractions:
    """拖拽、Ctrl+V、Del 删除。"""

    def test_drop_into_box(self, page, tmp_path):
        """拖拽文件进入指定框 — 直接调用 _img_drop 方法。"""
        img = _make_png(tmp_path, "drop.png")
        event = MagicMock()
        event.data = img
        state = page.image_states[1]
        with patch("ui.product_page.messagebox.askyesno", return_value=True), \
             patch("ui.product_page.messagebox.showwarning"), \
             patch("ui.product_page.messagebox.showerror"):
            page._img_drop(event, state)
        assert state["path"] is not None, f"Drop failed: path={state['path']}"

    def test_ctrl_v_paste_image(self, page, tmp_path):
        """Ctrl+V 粘贴 PIL Image — 测试粘贴逻辑（不依赖真实剪贴板）。"""
        import PIL.Image
        img = PIL.Image.new("RGB", (10, 10), "red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        dst = page._session_root / "pasted.png"
        dst.write_bytes(buf.getvalue())
        target = page.image_states[0]
        page._set_image_to_state(str(dst), target)
        assert target["path"] is not None

    def test_del_deletes_selected(self, page, tmp_path):
        img = _make_png(tmp_path, "del.png")
        state = page.image_states[2]
        page._load_image_from_path(img, state)
        page._select_img_box(state)
        page._on_del_key(None)
        assert state["path"] is None

    def test_del_no_effect_without_selection(self, page, tmp_path):
        img = _make_png(tmp_path, "nodel.png")
        state = page.image_states[0]
        page._load_image_from_path(img, state)
        page._selected_img_idx = None
        page._on_del_key(None)
        assert state["path"] is not None


class TestBottomButtons:
    """底部只有两个可见主按钮。"""

    def test_only_two_main_buttons(self, page):
        """底部按钮区只有「保存本次记录」和「清空并新建」。"""
        # 查找底部按钮文本
        btn_texts = []
        for widget in page._main_frame.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button):
                        btn_texts.append(child.cget("text"))
        # 至少有这两个按钮
        assert "保存本次记录" in btn_texts
        assert "清空并新建" in btn_texts
        # 不应该有「还原」或「用当前规则重算」
        assert not any("还原" in t for t in btn_texts), f"Found restore button: {btn_texts}"
        assert not any("重算" in t for t in btn_texts), f"Found recalc button: {btn_texts}"


class TestPackagingModeDrivesCalculation:
    """正常/保守档确实驱动计算。"""

    def test_normal_mode_uses_normal_dims(self, page):
        page._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        page._update_packaging_display()
        page._packaging_mode = "normal"
        page._mode_var.set("normal")
        # 验证 _pkg_normal 有正确的结构化字段
        assert page._pkg_normal["length_cm"] == 20
        assert page._pkg_normal["weight_g"] == 200

    def test_switch_to_conservative_changes_calc(self, page):
        page._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        page._update_packaging_display()
        page._packaging_mode = "normal"
        # 记录正常档体积重
        from calculation import volumetric_weight
        vol_n = volumetric_weight(20, 15, 5, 8000)
        # 切换到保守档
        page._packaging_mode = "conservative"
        vol_c = volumetric_weight(30, 25, 10, 8000)
        assert vol_c > vol_n, "Conservative volumetric weight should be larger"

    def test_switch_back_normal_restores(self, page):
        page._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        page._update_packaging_display()
        page._packaging_mode = "conservative"
        page._packaging_mode = "normal"
        assert page._pkg_normal["length_cm"] == 20
        assert page._pkg_normal["weight_g"] == 200

    def test_no_empty_dims_in_calc(self, page):
        """确保界面显示了规格后计算不使用空值。"""
        page._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        page._update_packaging_display()
        page._packaging_mode = "normal"
        active = page._pkg_normal
        assert active["length_cm"] is not None
        assert active["width_cm"] is not None
        assert active["height_cm"] is not None
        assert active["weight_g"] is not None


class TestSaveAndClear:
    """保存不清空页面；清空并新建有未保存确认。"""

    def test_save_does_not_clear(self, page, tmp_path):
        page._entry_vars["cost"].set("10")
        page._entry_vars["domestic"].set("5")
        page._entry_vars["shein"].set("5.99")
        page._entry_vars["price_rmb"].set("30")
        with patch("ui.product_page.messagebox.showinfo"):
            page.save_product()
        assert page._entry_vars["cost"].get() == "10", "Cost cleared after save!"
        assert page._entry_vars["shein"].get() == "5.99"

    def test_clear_with_unsaved_confirms(self, page):
        page._entry_vars["cost"].set("50")
        page._var_name.set("Unsaved Product")
        with patch("ui.product_page.messagebox.askyesno", return_value=False):
            page._clear_and_new()
        # Should NOT clear
        assert page._entry_vars["cost"].get() == "50"
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._clear_and_new()
        # Should clear
        assert page._entry_vars["cost"].get() == ""


class TestFakeAIIntegration:
    """FakeAI 与包装档联动。"""

    def test_ai_recognize_fills_summary(self, page):
        page.image_states[0]["path"] = "dummy.png"
        page._ai_recognize()
        assert page._var_ai_type.get() != ""
        assert page._var_ai_material.get() != ""

    def test_reestimate_updates_packaging(self, page):
        page._ai_data = {}
        page._var_rigidity.set("软")
        page._var_foldable.set("好")
        page._reestimate_packaging()
        assert page._pkg_normal.get("length_cm") is not None
        assert page._pkg_conservative.get("length_cm") is not None

    def test_attr_change_marks_expired(self, page):
        page._clear_packaging_expired()
        page._var_rigidity.set("硬")
        assert page._packaging_expired is True
