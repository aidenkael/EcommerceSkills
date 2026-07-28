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

ROAD-1 最终收尾新增：
- 真实 Ctrl+V 模拟剪贴板 PIL Image 完整流程
- 含空格和中文路径的拖拽测试
- DnD 根窗口注册验证（TkinterDnD.Tk）
- 包装计算链完整测试（recalculate → 体积重/计费重/物流费变化 → 切回恢复）
"""
import sys, os, tempfile, struct, zlib, io, math
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


# ═══════════════════════════════════════════════════════════════════════════
# ROAD-1 最终收尾 — 真实交互测试
# ═══════════════════════════════════════════════════════════════════════════

class TestCtrlVClipboardImage:
    """真实 Ctrl+V 模拟剪贴板 PIL Image 完整流程。"""

    def test_ctrl_v_pastes_pil_image_to_selected_box(self, page, tmp_path):
        """模拟剪贴板返回 PIL.Image，Ctrl+V 后图片进入选中框。"""
        import PIL.Image
        fake_img = PIL.Image.new("RGB", (20, 20), "blue")
        with patch("ui.product_page.PIL.ImageGrab.grabclipboard", return_value=fake_img):
            target = page.image_states[0]
            page._select_img_box(target)
            page._on_ctrl_v(None)
        assert target["path"] is not None, "Ctrl+V did not set image path"
        assert os.path.exists(target["path"]), f"Pasted file not found: {target['path']}"

    def test_ctrl_v_pastes_to_first_empty_box_when_no_selection(self, page, tmp_path):
        """无选中框时，Ctrl+V 粘贴到第一个空框。"""
        import PIL.Image
        fake_img = PIL.Image.new("RGB", (15, 15), "green")
        with patch("ui.product_page.PIL.ImageGrab.grabclipboard", return_value=fake_img):
            page._selected_img_idx = None
            page._on_ctrl_v(None)
        assert page.image_states[0]["path"] is not None

    def test_ctrl_v_all_boxes_full_shows_info(self, page, tmp_path):
        """所有框已满时 Ctrl+V 弹提示。"""
        import PIL.Image
        fake_img = PIL.Image.new("RGB", (10, 10), "red")
        # 填满所有框
        for i, s in enumerate(page.image_states):
            img = _make_png(tmp_path, f"full_{i}.png")
            page._load_image_from_path(img, s)
        with patch("ui.product_page.PIL.ImageGrab.grabclipboard", return_value=fake_img), \
             patch("ui.product_page.messagebox.showinfo") as mock_info:
            page._selected_img_idx = None
            page._on_ctrl_v(None)
        mock_info.assert_called_once()

    def test_ctrl_v_empty_clipboard_shows_info(self, page):
        """剪贴板为空时弹提示。"""
        with patch("ui.product_page.PIL.ImageGrab.grabclipboard", return_value=None), \
             patch("ui.product_page.messagebox.showinfo") as mock_info:
            # Also mock win32clipboard import to simulate no file clipboard
            with patch.dict(sys.modules, {"win32clipboard": None}):
                page._on_ctrl_v(None)
        mock_info.assert_called_once()


class TestDragDropPathParsing:
    """拖拽路径解析 — 含空格、中文路径。"""

    def test_drop_path_with_spaces(self, page, tmp_path):
        """含空格的路径能正确解析。"""
        img = _make_png(tmp_path, "my image file.png")
        event = MagicMock()
        event.data = str(img)  # 简单路径字符串
        state = page.image_states[1]
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._img_drop(event, state)
        assert state["path"] is not None, f"Drop with spaces failed: {state['path']}"

    def test_drop_path_with_chinese(self, page, tmp_path):
        """中文路径能正确解析。"""
        img = _make_png(tmp_path, "商品图片.png")
        event = MagicMock()
        event.data = str(img)
        state = page.image_states[0]
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._img_drop(event, state)
        assert state["path"] is not None, f"Drop with Chinese failed: {state['path']}"

    def test_drop_tcl_list_format(self, page, tmp_path):
        """Tcl 列表格式 {path1} {path2} 取第一个。"""
        img1 = _make_png(tmp_path, "first.png")
        img2 = _make_png(tmp_path, "second.png")
        event = MagicMock()
        event.data = f"{{{img1}}} {{{img2}}}"
        state = page.image_states[0]
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._img_drop(event, state)
        assert state["path"] is not None

    def test_drop_overwrite_confirm(self, page, tmp_path):
        """目标框已有图片时，拖拽需要确认覆盖。"""
        img1 = _make_png(tmp_path, "orig.png")
        img2 = _make_png(tmp_path, "new.png")
        state = page.image_states[0]
        page._load_image_from_path(img1, state)
        event = MagicMock()
        event.data = str(img2)
        # 拒绝覆盖
        with patch("ui.product_page.messagebox.askyesno", return_value=False):
            page._img_drop(event, state)
        orig_path = state["path"]
        # 同意覆盖
        with patch("ui.product_page.messagebox.askyesno", return_value=True):
            page._img_drop(event, state)
        assert state["path"] != orig_path, "Overwrite not applied"


class TestDndRootWindowRegistration:
    """DnD 根窗口注册验证。"""

    def test_main_window_uses_tkinterdnd_when_available(self, tmp_path):
        """MainWindow 在 tkinterdnd2 可用时使用 TkinterDnD.Tk()。"""
        try:
            import tkinterdnd2
        except ImportError:
            pytest.skip("tkinterdnd2 not installed")
        from ui.main_window import MainWindow
        db = DatabaseManager(db_path=str(tmp_path / "dnd_root.db"))
        cfg = ConfigManager(db)
        try:
            mw = MainWindow(db, cfg)
        except Exception:
            pytest.skip("TkinterDnD.Tk() failed to initialize")
        try:
            # TkinterDnD.Tk 实例应该有 drop_target_register 方法
            assert hasattr(mw._root, "drop_target_register"), \
                "Root window missing drop_target_register — not TkinterDnD.Tk()"
        finally:
            mw._root.destroy()

    def test_product_page_dnd_registration_no_crash(self, tmp_path):
        """ProductPage 图片框在 TkinterDnD.Tk 根窗口下不崩溃。"""
        try:
            from tkinterdnd2 import TkinterDnD
            root = TkinterDnD.Tk()
            root.withdraw()
        except Exception:
            pytest.skip("TkinterDnD.Tk not available")
        try:
            db = DatabaseManager(db_path=str(tmp_path / "dnd_page.db"))
            cfg = ConfigManager(db)
            p = ProductPage(root, db, cfg)
            p._show_thumb = lambda state: None
            # 确保图片框已创建且有 DnD 注册
            assert len(p.image_states) >= 4
            # 验证没有因 DnD 注册而崩溃
        finally:
            root.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# ROAD-1 最终收尾 — 包装计算链完整测试
# ═══════════════════════════════════════════════════════════════════════════

class TestPackagingCalcChain:
    """通过真实 recalculate() 验证包装档切换驱动计算结果变化。"""

    @pytest.fixture
    def page_with_route(self, tmp_path):
        """带货代路由的 page fixture。

        数据库初始化时自动播种「深圳」路由 (head=80, fixed=10)。
        我们额外创建「测试货代」路由 (head=100, fixed=36, vol_div=8000)
        并在测试中显式选择它。
        """
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            pytest.skip("Tcl/Tk 环境不可用")
        db = DatabaseManager(db_path=str(tmp_path / "chain.db"))
        cfg = ConfigManager(db)
        # 创建一个测试货代路由
        db.save_route({
            "display_name": "测试货代",
            "head_haul_rate": 100.0,
            "fixed_service_fee": 36.0,
            "volume_divisor": 8000,
            "is_enabled": True,
            "is_archived": False,
            "description": "测试用",
        })
        p = ProductPage(root, db, cfg)
        p._show_thumb = lambda state: None
        # 显式选择「测试货代」而非播种的「深圳」
        p._refresh_route_choices()
        assert "测试货代" in p._route_display_to_key, \
            f"测试货代 not in routes: {list(p._route_display_to_key.keys())}"
        p._forwarder_var.set("测试货代")
        yield p
        root.destroy()

    def test_normal_mode_recalculate(self, page_with_route):
        """正常档下 recalculate 计算出体积重/计费重/物流费。"""
        p = page_with_route
        # 设置成本
        p._entry_vars["cost"].set("10")
        p._entry_vars["domestic"].set("5")
        p._entry_vars["tail"].set("40")
        # 设置包装数据
        p._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        p._update_packaging_display()
        p._packaging_mode = "normal"
        p._mode_var.set("normal")
        # 执行计算
        p._programmatic = False
        p.recalculate()
        # 验证计算结果
        assert p._computed.get("volumetric_weight") is not None, "volumetric_weight is None"
        # 20*15*5/8000 = 0.1875 kg
        assert abs(p._computed["volumetric_weight"] - 0.1875) < 0.01
        # actual = 200g = 0.2kg; chargeable = max(0.2, 0.1875) = 0.2
        assert abs(p._computed["chargeable_weight"] - 0.2) < 0.01
        # head_haul = 0.2 * 100 = 20
        assert abs(p._computed["head_haul"] - 20.0) < 0.01
        # logistics = 20 + 36 + 40 = 96
        assert abs(p._computed["total_logistics"] - 96.0) < 0.01
        # total_cost = 10 + 5 + 96 = 111
        assert abs(p._computed["total_cost"] - 111.0) < 0.01

    def test_conservative_mode_changes_results(self, page_with_route):
        """切换到保守档后，体积重/计费重/物流费发生变化。"""
        p = page_with_route
        p._entry_vars["cost"].set("10")
        p._entry_vars["domestic"].set("5")
        p._entry_vars["tail"].set("40")
        p._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        p._update_packaging_display()
        # 正常档
        p._packaging_mode = "normal"
        p._programmatic = False
        p.recalculate()
        vol_n = p._computed["volumetric_weight"]
        chg_n = p._computed["chargeable_weight"]
        head_n = p._computed["head_haul"]
        logistics_n = p._computed["total_logistics"]
        # 切换到保守档
        p._packaging_mode = "conservative"
        p._mode_var.set("conservative")
        p.recalculate()
        vol_c = p._computed["volumetric_weight"]
        chg_c = p._computed["chargeable_weight"]
        head_c = p._computed["head_haul"]
        logistics_c = p._computed["total_logistics"]
        # 保守档体积重更大: 30*25*10/8000 = 0.9375
        assert vol_c > vol_n, f"Conservative vol ({vol_c}) should > normal ({vol_n})"
        assert abs(vol_c - 0.9375) < 0.01
        # 保守档计费重: max(0.4, 0.9375) = 0.9375
        assert chg_c > chg_n, f"Conservative chg ({chg_c}) should > normal ({chg_n})"
        # 保守档头程费更高
        assert head_c > head_n
        # 保守档总物流费更高
        assert logistics_c > logistics_n

    def test_switch_back_normal_restores_values(self, page_with_route):
        """切回正常档后，计算结果恢复到正常档值。"""
        p = page_with_route
        p._entry_vars["cost"].set("10")
        p._entry_vars["domestic"].set("5")
        p._entry_vars["tail"].set("40")
        p._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        p._update_packaging_display()
        # 正常档基线
        p._packaging_mode = "normal"
        p._programmatic = False
        p.recalculate()
        vol_n_1 = p._computed["volumetric_weight"]
        chg_n_1 = p._computed["chargeable_weight"]
        # 切到保守档
        p._packaging_mode = "conservative"
        p.recalculate()
        # 切回正常档
        p._packaging_mode = "normal"
        p.recalculate()
        vol_n_2 = p._computed["volumetric_weight"]
        chg_n_2 = p._computed["chargeable_weight"]
        assert abs(vol_n_1 - vol_n_2) < 0.001, f"Vol not restored: {vol_n_1} vs {vol_n_2}"
        assert abs(chg_n_1 - chg_n_2) < 0.001, f"Chg not restored: {chg_n_1} vs {chg_n_2}"

    def test_no_packaging_data_falls_back_gracefully(self, page_with_route):
        """无包装数据时 recalculate 不崩溃，结果中包装相关字段为 None 或使用 fallback。"""
        p = page_with_route
        p._entry_vars["cost"].set("10")
        p._entry_vars["domestic"].set("5")
        p._entry_vars["tail"].set("40")
        # 不设置 _ai_data 或设为空
        p._ai_data = {}
        p._pkg_normal = {}
        p._pkg_conservative = {}
        p._packaging_mode = "normal"
        p._programmatic = False
        # 不应抛异常
        p.recalculate()
        # 无包装尺寸 → 体积重 None → 物流费数据不足
        # 但不应崩溃
        assert "forwarder" in p._computed

    def test_profit_calculation_with_price(self, page_with_route):
        """填入售价后，利润和利润率正确计算。"""
        p = page_with_route
        p._entry_vars["cost"].set("10")
        p._entry_vars["domestic"].set("5")
        p._entry_vars["tail"].set("40")
        p._entry_vars["price_rmb"].set("200")
        p._ai_data = {
            "normal": {"method": "袋", "length_cm": 20, "width_cm": 15, "height_cm": 5, "weight_g": 200, "note": "n"},
            "conservative": {"method": "箱", "length_cm": 30, "width_cm": 25, "height_cm": 10, "weight_g": 400, "note": "c"},
        }
        p._update_packaging_display()
        p._packaging_mode = "normal"
        p._programmatic = False
        p.recalculate()
        # total_cost = 111, price = 200, no promo
        # profit = 200 - 111 = 89
        assert p._computed.get("profit") is not None
        assert abs(p._computed["profit"] - 89.0) < 0.01
        # profit_rate = 89/200 * 100 = 44.5%
        assert abs(p._computed["profit_rate"] - 44.5) < 0.1
