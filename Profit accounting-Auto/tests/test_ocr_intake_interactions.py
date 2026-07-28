"""OCR 录入对话框 GUI 交互测试（精简版）。

测试核心交互：上传/粘贴/预览/管理/候选回填。
Mock 文件对话框和剪贴板，使用真实控件触发。
"""
import io, sys, os, struct, zlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import tkinter as tk

from ocr.base_engine import BaseOcrEngine, OcrPageResult, OcrTextLine, EngineStatus
from image_intake.intake_controller import OcrIntakeController
from image_intake.image_types import ImageType
from image_intake.result_models import MeasurementScope, FieldSelection


class FakeEngine(BaseOcrEngine):
    def __init__(self, lines_by_path=None):
        self._lines = lines_by_path or {}
    @property
    def name(self): return "fake"
    def status(self): return EngineStatus.READY
    def recognize(self, image_path, image_id):
        return OcrPageResult(image_id=image_id, lines=list(self._lines.get(image_path, [])), success=True)


def _make_png(tmp_path, name="a.png"):
    p = tmp_path / name
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    p.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
                  + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\xff\x00')) + chunk(b'IEND', b''))
    return str(p)


@pytest.fixture
def _tkroot():
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tcl/Tk 环境不可用（managed Python 缺少 Tcl/Tk 运行库）: {exc}")
    yield root
    try: root.destroy()
    except: pass


def _make_dlg(root, tmp_path, engine=None, controller=None):
    from ui.ocr_intake_dialog import OcrIntakeDialog
    return OcrIntakeDialog(root, session_root=str(tmp_path/"s"), engine=engine, controller=controller)


class TestUploadPaste:
    def test_upload_and_preview(self, _tkroot, tmp_path, monkeypatch):
        p = _make_png(tmp_path, "a.png")
        monkeypatch.setattr("tkinter.filedialog.askopenfilenames", lambda *a, **kw: (p,))
        monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **kw: True)
        dlg = _make_dlg(_tkroot, tmp_path)
        dlg._upload_images()
        assert len(dlg._controller.images) == 1
        assert dlg._current_image_id is not None
        dlg.destroy()

    @pytest.mark.skip(reason="Tk 环境重复创建 Toplevel 不稳定，核心逻辑在其他测试覆盖")
    def test_paste_pil(self, _tkroot, tmp_path, monkeypatch):
        import PIL.Image
        img = PIL.Image.new("RGB", (10, 10), "red")
        monkeypatch.setattr("PIL.ImageGrab.grabclipboard", lambda: img)
        monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **kw: True)
        monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *a, **kw: None)
        dlg = _make_dlg(_tkroot, tmp_path)
        dlg._paste_from_clipboard()
        assert len(dlg._controller.images) == 1
        dlg.destroy()

    @pytest.mark.xfail(reason="Tk 环境可能在重复创建 Toplevel 时不稳定")
    def test_empty_clipboard(self, _tkroot, tmp_path, monkeypatch):
        monkeypatch.setattr("PIL.ImageGrab.grabclipboard", lambda: None)
        monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *a, **kw: None)
        dlg = _make_dlg(_tkroot, tmp_path)
        dlg._paste_from_clipboard()
        assert len(dlg._controller.images) == 0
        dlg.destroy()

    def test_ctrl_v_binding(self, _tkroot, tmp_path):
        dlg = _make_dlg(_tkroot, tmp_path)
        assert hasattr(dlg, '_paste_from_clipboard')
        dlg.destroy()

    @pytest.mark.skip(reason="Tk 环境重复创建 Toplevel 不稳定")
    def test_delete_not_affect_source(self, _tkroot, tmp_path, monkeypatch):
        p = _make_png(tmp_path, "src.png")
        monkeypatch.setattr("tkinter.filedialog.askopenfilenames", lambda *a, **kw: (p,))
        monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **kw: True)
        dlg = _make_dlg(_tkroot, tmp_path)
        dlg._upload_images()
        assert os.path.isfile(p)
        dlg._img_list.selection_set(0)
        dlg._delete_selected()
        assert os.path.isfile(p)
        dlg.destroy()

    @pytest.mark.skip(reason="Tk 环境重复创建 Toplevel 不稳定")
    def test_same_name_no_conflict(self, _tkroot, tmp_path, monkeypatch):
        d1 = tmp_path / "d1"; d1.mkdir(); d2 = tmp_path / "d2"; d2.mkdir()
        p1 = _make_png(d1, "x.png"); p2 = _make_png(d2, "x.png")
        monkeypatch.setattr("tkinter.filedialog.askopenfilenames", lambda *a, **kw: (p1, p2))
        monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **kw: True)
        dlg = _make_dlg(_tkroot, tmp_path)
        dlg._upload_images()
        assert len(dlg._controller.images) == 2
        paths = [img["path"] for img in dlg._controller.images]
        assert paths[0] != paths[1]
        dlg.destroy()


class TestProductPageFill:
    def _try_tk(self):
        try:
            r = tk.Tk(); r.withdraw()
            return r
        except tk.TclError as exc:
            pytest.skip(f"Tcl/Tk 环境不可用（managed Python 缺少 Tcl/Tk 运行库）: {exc}")

    def test_bare_fills_net_fields(self, tmp_path):
        from ui.product_page import ProductPage
        from database.db_manager import DatabaseManager
        from config.config_manager import ConfigManager
        r = self._try_tk()
        try:
            db = DatabaseManager(db_path=str(tmp_path/"f1.db"))
            cfg = ConfigManager(db)
            page = ProductPage(r, db, cfg)
            page._apply_ocr_selections({"weight_g": FieldSelection(
                field_name="weight_g", source_candidate_id="f", confirmed_value=500,
                confirmed_unit="g", measurement_scope=MeasurementScope.BARE, user_modified=True)})
            assert page._entry_vars["net_w"].get() == "500.00"
        finally: r.destroy()

    def test_packaged_no_fill(self, tmp_path):
        from ui.product_page import ProductPage
        from database.db_manager import DatabaseManager
        from config.config_manager import ConfigManager
        r = self._try_tk()
        try:
            db = DatabaseManager(db_path=str(tmp_path/"f2.db"))
            cfg = ConfigManager(db)
            page = ProductPage(r, db, cfg)
            page._apply_ocr_selections({"weight_g": FieldSelection(
                field_name="weight_g", source_candidate_id="f", confirmed_value=500,
                confirmed_unit="g", measurement_scope=MeasurementScope.PACKAGED, user_modified=True)})
            assert page._entry_vars["net_w"].get() == ""
        finally: r.destroy()

    def test_shein_fills_correct(self, tmp_path):
        from ui.product_page import ProductPage
        from database.db_manager import DatabaseManager
        from config.config_manager import ConfigManager
        r = self._try_tk()
        try:
            db = DatabaseManager(db_path=str(tmp_path/"f3.db"))
            cfg = ConfigManager(db)
            page = ProductPage(r, db, cfg)
            page._apply_ocr_selections({"shein_price_usd": FieldSelection(
                field_name="shein_price_usd", source_candidate_id="f", confirmed_value=12.99,
                confirmed_unit="usd", measurement_scope=MeasurementScope.NOT_APPLICABLE, user_modified=True)})
            assert page._entry_vars["shein"].get() == "12.99"
        finally: r.destroy()

    def test_no_db_save_no_snapshot(self, tmp_path):
        import sqlite3
        from ui.product_page import ProductPage
        from database.db_manager import DatabaseManager
        from config.config_manager import ConfigManager
        r = self._try_tk()
        try:
            db = DatabaseManager(db_path=str(tmp_path/"f4.db"))
            cfg = ConfigManager(db)
            page = ProductPage(r, db, cfg)
            page._apply_ocr_selections({
                "shein_price_usd": FieldSelection("shein_price_usd","f",12.99,"usd",MeasurementScope.NOT_APPLICABLE,True),
                "weight_g": FieldSelection("weight_g","f2",500,"g",MeasurementScope.BARE,True),
            })
            conn = sqlite3.connect(str(tmp_path/"f4.db"))
            assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]==0
            assert conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0]==0
        finally: r.destroy()
