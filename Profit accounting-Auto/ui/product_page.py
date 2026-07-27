"""
新商品测算页面 — ROAD-1 重构版

8 大区域竖向布局（按最终 UI 基准图）：
  1. 图片输入区（图片框 placeholder, Step 2 实现）
  2. AI 识别摘要（Fake AI placeholder, Step 3 实现）
  3. 成本与裸件信息
  4. 正常/保守包装档（双列）
  5. 货代方案
  6. 系统总成本（只读）
  7. 利润测算
  8. 底部操作区（保存本次记录 / 清空并新建）

保留原有：计算引擎、配置读写、数据库快照、规则上下文。
"""

import math, tkinter as tk, sys, os, shutil, uuid
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

try:
    import PIL.Image, PIL.ImageTk, PIL.ImageGrab
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from calculation import (
    volumetric_weight, chargeable_weight, head_haul_cost,
    total_logistics_cost, known_logistics_subtotal,
    total_cost, known_total_cost_subtotal,
    profit_amount, profit_rate, suggested_price_from_rate,
    net_profit_amount, net_profit_rate, rmb_to_usd, usd_to_rmb, evaluate_rule,
    compare_rule_contexts,
)
from config.config_manager import VOLUME_DIVISOR, FORWARDER_LABELS
from database.db_manager import CALCULATION_SCHEMA_VERSION
from image_intake.result_models import MeasurementScope
from adapters.fake_vision import FakeVisionAdapter


# ─── helpers ────────────────────────────────────────────────────────────────

def _safe_float(val):
    if val is None or str(val).strip() == "": return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f): return None
        return f
    except (ValueError, TypeError): return None

def _is_valid_number(val):
    s = str(val).strip() if val is not None else ""
    if s == "": return True
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f): return False
        return f >= 0
    except (ValueError, TypeError): return False

def _is_valid_rate(val):
    s = str(val).strip() if val is not None else ""
    if s == "": return True
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f): return False
        return 0 <= f < 100
    except (ValueError, TypeError): return False


def _fmt(value, decimals=2):
    if value is None: return ""
    return f"{value:.{decimals}f}"


# ─── Section Header Widget ──────────────────────────────────────────────────

class SectionHeader(ttk.Frame):
    """带标题和说明文字的区域标题。"""
    def __init__(self, parent, title, subtitle=""):
        super().__init__(parent)
        lbl = ttk.Label(self, text=title, font=("Microsoft YaHei", 11, "bold"))
        lbl.pack(side=tk.LEFT, padx=(5, 10))
        if subtitle:
            ttk.Label(self, text=subtitle, foreground="#888", font=("", 8)).pack(side=tk.LEFT)


class ProductPage(ttk.Frame):
    def __init__(self, parent, db_manager, config_manager):
        super().__init__(parent)
        self._db = db_manager
        self._cfg = config_manager
        self._product_id = None
        self._calc_direction = None
        self._last_modified = None
        self._programmatic = False
        self._ocr_dialog_factory = None
        self._ocr_controller = None
        self._has_snapshot = False
        self._saved_rule_context = None
        self._show_rate_banner = False
        self._computed = {}
        self._entry_vars = {}
        self._entry_widgets = {}
        self._weight_unit_version = "g_v1"
        self._weight_confirmed = True
        self._saved_profit_rule = None
        self._profit_rule_source = "none"
        self._profit_rule_explicitly_changed = False
        self._profit_rule_unavailable_notice = False
        # Step 2 图片框系统
        self.image_states = []
        self._init_session()
        # Step 3 AI / 包装档占位
        self._ai_data = {}
        self._packaging_mode = "normal"  # "normal" | "conservative"
        self._packaging_expired = False
        self._pkg_normal = {}
        self._pkg_conservative = {}
        self._build_ui()
        self.new_product()

    # ─── UI 构建 ────────────────────────────────────────────────────────────

    def _build_ui(self):
        # 主容器：左侧 scrollable 主区域 + 底部按钮
        self._outer = ttk.Frame(self)
        self._outer.pack(fill=tk.BOTH, expand=True)

        # 可滚动画布
        canvas = tk.Canvas(self._outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._outer, orient=tk.VERTICAL, command=canvas.yview)
        self._main_frame = ttk.Frame(canvas)
        self._main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # 8 大区域
        self._build_section_images()
        self._build_section_ai()
        self._build_section_cost_bare()
        self._build_section_packaging()
        self._build_section_forwarders()
        self._build_section_total_cost()
        self._build_section_profit()
        self._build_section_bottom()

    def _section_frame(self, title, subtitle=""):
        container = ttk.Frame(self._main_frame)
        container.pack(fill=tk.X, padx=10, pady=(8, 2))
        SectionHeader(container, title, subtitle).pack(fill=tk.X, anchor=tk.W)
        body = ttk.Frame(self._main_frame)
        body.pack(fill=tk.X, padx=10, pady=(0, 8))
        return body

    # ─── Session 管理 ─────────────────────────────────────────────────

    def _init_session(self):
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        base = Path(local) / "ProfitAccountingAuto" / "image_sessions"
        self._session_root = base / (datetime.now().strftime("session_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
        self._session_root.mkdir(parents=True, exist_ok=True)

    def _copy_image_to_session(self, src_path):
        dst = self._session_root / (uuid.uuid4().hex + (Path(src_path).suffix.lower() or ".png"))
        shutil.copy2(src_path, dst)
        return str(dst)

    # ─── section 1：图片输入（完整实现）───────────────────────────────────

    IMG_TYPES = ["主图", "商品信息", "尺寸/重量"]

    def _build_section_images(self):
        body = self._section_frame("图片输入", "上传、拖入或粘贴商品图片")
        self._img_container = ttk.Frame(body)
        self._img_container.pack(fill=tk.X, pady=5)
        self._selected_img_idx = None
        self._rebuild_image_boxes()
        # 图片框数量调节（+/-）
        ctrl = ttk.Frame(body)
        ctrl.pack(anchor=tk.W, pady=(2, 0))
        ttk.Label(ctrl, text="图片框数量：", font=("", 8)).pack(side=tk.LEFT)
        self._img_count_var = tk.StringVar(value="5")
        ttk.Label(ctrl, textvariable=self._img_count_var, font=("", 9, "bold")).pack(side=tk.LEFT, padx=3)
        ttk.Button(ctrl, text="－", width=2, command=self._img_decrease).pack(side=tk.LEFT, padx=1)
        ttk.Button(ctrl, text="＋", width=2, command=self._img_increase).pack(side=tk.LEFT, padx=1)
        ttk.Label(ctrl, text="(最少3框，最多6框；点击框选中后按Del删除)", foreground="#888", font=("", 8)).pack(side=tk.LEFT, padx=5)
        # 全局键盘绑定
        self.bind_all("<Control-v>", self._on_ctrl_v)
        self.bind_all("<Delete>", self._on_del_key)

    def _rebuild_image_boxes(self):
        """根据当前 _img_count_var 重建图片框，保留已有图片/类型。"""
        # 保存当前状态
        old_states = getattr(self, "image_states", [])
        saved = []
        for s in old_states:
            saved.append({"path": s.get("path"), "img_type": s.get("type_var", tk.StringVar()).get() if hasattr(s.get("type_var", None), "get") else "主图"})
        for child in self._img_container.winfo_children():
            child.destroy()
        self.image_states = []
        count = int(self._img_count_var.get()) if hasattr(self, "_img_count_var") else 5
        for i in range(count):
            old = saved[i] if i < len(saved) else None
            self._create_image_box(i, old)

    def _create_image_box(self, idx, saved_state=None):
        frm = ttk.LabelFrame(self._img_container, text=f"框 {idx+1}", width=140, height=170)
        frm.grid(row=0, column=idx, padx=3, pady=3, sticky="n")
        frm.grid_propagate(False)

        # 类型选择
        type_val = saved_state["img_type"] if saved_state else "主图"
        type_var = tk.StringVar(value=type_val)
        cb = ttk.Combobox(frm, textvariable=type_var, values=self.IMG_TYPES, state="readonly", width=8)
        cb.pack(anchor=tk.N, pady=2)

        # 图片标签
        lbl = ttk.Label(frm, text="点击上传\n或拖入图片\n或 Ctrl+V", foreground="#999", font=("", 8))
        lbl.pack(anchor=tk.CENTER, expand=True, fill=tk.BOTH, padx=4, pady=4)

        state = {"frame": frm, "label": lbl, "type_var": type_var, "path": None, "photo": None, "idx": idx}
        self.image_states.append(state)

        # 恢复已有图片
        if saved_state and saved_state.get("path"):
            state["path"] = saved_state["path"]
            self._show_thumb(state)

        # 选中事件
        def _select(e, s=state):
            self._select_img_box(s)
        frm.bind("<Button-1>", _select)
        lbl.bind("<Button-1>", _select)

        # 上传（双击或直接点击空框）
        frm.bind("<Double-Button-1>", lambda e, s=state: self._img_upload(s))
        lbl.bind("<Double-Button-1>", lambda e, s=state: self._img_upload(s))

        # 右键菜单
        menu = tk.Menu(frm, tearoff=0)
        menu.add_command(label="上传图片", command=lambda s=state: self._img_upload(s))
        menu.add_command(label="清除图片", command=lambda s=state: self._img_delete(s))
        menu.add_command(label="预览大图", command=lambda s=state: self._img_preview(s))
        frm.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))

        # 拖拽支持 (tkinterdnd2)
        if _DND_AVAILABLE:
            frm.drop_target_register(DND_FILES)
            frm.dnd_bind("<<Drop>>", lambda e, s=state: self._img_drop(e, s))

        # 修改类型触发 AI 过期
        type_var.trace_add("write", lambda *_, s=state: self._on_img_type_changed(s))

    def _select_img_box(self, state):
        """选中图片框，高亮边框。"""
        self._selected_img_idx = state["idx"]
        for s in self.image_states:
            try:
                s["frame"].configure(style="TLabelFrame")
            except Exception:
                pass
        try:
            state["frame"].configure(style="Selected.TLabelFrame")
        except Exception:
            pass

    def _on_del_key(self, event):
        """Del 键删除当前选中图片框中的图片。"""
        if self._selected_img_idx is None:
            return
        if self._selected_img_idx < len(self.image_states):
            state = self.image_states[self._selected_img_idx]
            if state["path"] is not None:
                self._img_delete(state)

    def _on_ctrl_v(self, event):
        """Ctrl+V 粘贴剪贴板图片到当前选中框（或第一个空框）。"""
        target = None
        if self._selected_img_idx is not None and self._selected_img_idx < len(self.image_states):
            target = self.image_states[self._selected_img_idx]
        else:
            for s in self.image_states:
                if s["path"] is None:
                    target = s
                    break
        if target is None:
            messagebox.showinfo("提示", "所有图片框已满，请先删除一个。")
            return
        if not _PIL_AVAILABLE:
            messagebox.showerror("错误", "PIL 不可用，无法粘贴。")
            return
        try:
            img = PIL.ImageGrab.grabclipboard()
        except Exception as exc:
            messagebox.showerror("粘贴失败", str(exc))
            return
        if img is None:
            # 可能是文件路径
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                file_list = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                win32clipboard.CloseClipboard()
                if file_list:
                    for f in file_list:
                        ext = Path(f).suffix.lower()
                        if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                            self._load_image_from_path(f, target)
                            return
            except ImportError:
                pass
            messagebox.showinfo("提示", "剪贴板中没有图片。")
            return
        # PIL Image → 保存到临时会话
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        dst = self._session_root / (uuid.uuid4().hex + ".png")
        dst.write_bytes(buf.getvalue())
        self._set_image_to_state(str(dst), target)

    def _img_drop(self, event, state):
        """tkinterdnd2 拖拽文件放入图片框。"""
        files = self._tk.splitlist(event.data)
        if not files:
            return
        f = files[0].strip("{}")
        self._load_image_from_path(f, state)

    def _load_image_from_path(self, path, state):
        """从文件路径加载图片到指定图片框。"""
        ext = Path(path).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            messagebox.showwarning("不支持", f"不支持的文件类型: {ext}")
            return
        if state["path"] is not None:
            if not messagebox.askyesno("覆盖确认", "该图片框已有图片，确定覆盖吗？"):
                return
        try:
            new_path = self._copy_image_to_session(path)
        except Exception as exc:
            messagebox.showerror("上传失败", str(exc))
            return
        self._set_image_to_state(new_path, state)

    def _set_image_to_state(self, path, state):
        """设置图片路径到 state 并显示缩略图。"""
        state["path"] = path
        self._show_thumb(state)

    def _img_upload(self, state):
        f = filedialog.askopenfilename(parent=self, title="选择图片",
                                         filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if not f:
            return
        if state["path"] is not None:
            if not messagebox.askyesno("覆盖确认", "该图片框已有图片，确定覆盖吗？"):
                return
        try:
            new_path = self._copy_image_to_session(f)
        except Exception as exc:
            messagebox.showerror("上传失败", str(exc)); return
        self._set_image_to_state(new_path, state)

    def _show_thumb(self, state):
        """在图片框中显示缩略图。"""
        if not _PIL_AVAILABLE:
            state["label"].configure(text=f"已加载:\n{Path(state['path']).name}", foreground="#2a6496")
            return
        try:
            img = PIL.Image.open(state["path"])
            frm = state["frame"]
            w = frm.winfo_width() or 120
            h = frm.winfo_height() or 140
            img.thumbnail((w - 10, h - 30), PIL.Image.LANCZOS if hasattr(PIL.Image, "LANCZOS") else 1)
            photo = PIL.ImageTk.PhotoImage(img)
            state["photo"] = photo
            state["label"].configure(image=photo, text="", compound=tk.CENTER)
            state["label"].image = photo
        except Exception:
            state["label"].configure(text=f"已加载:\n{Path(state['path']).name}", foreground="#2a6496")

    def _img_delete(self, state):
        if state["path"] is None: return
        state["path"] = None; state["photo"] = None
        state["label"].configure(image="", text="点击上传\n或拖入图片\n或 Ctrl+V", foreground="#999", compound=tk.CENTER)

    def _img_preview(self, state):
        if state["path"] is None:
            messagebox.showinfo("提示", "此框暂无图片"); return
        if _PIL_AVAILABLE:
            try:
                img = PIL.Image.open(state["path"])
                # 弹出独立窗口预览
                top = tk.Toplevel(self)
                top.title("图片预览")
                photo = PIL.ImageTk.PhotoImage(img)
                lbl = ttk.Label(top, image=photo)
                lbl.image = photo
                lbl.pack(padx=5, pady=5)
                top.focus_force()
            except Exception as exc:
                messagebox.showinfo("图片路径", f"{state['path']}\n\n错误: {exc}")
        else:
            messagebox.showinfo("图片路径", state["path"])

    def _on_img_type_changed(self, state):
        self._mark_packaging_expired()

    def _img_decrease(self):
        cur = int(self._img_count_var.get())
        if cur <= 3:
            return
        # 检查末尾框是否有图片
        last_idx = cur - 1
        if last_idx < len(self.image_states):
            last_state = self.image_states[last_idx]
            if last_state["path"] is not None:
                if not messagebox.askyesno("确认减少", f"框 {last_idx+1} 含有图片，确定减少并清除该图片吗？\n（用户原始文件不会被删除）"):
                    return
        self._img_count_var.set(str(cur - 1))
        self._rebuild_image_boxes()

    def _img_increase(self):
        cur = int(self._img_count_var.get())
        if cur >= 6:
            return
        self._img_count_var.set(str(cur + 1))
        self._rebuild_image_boxes()

    # ─── section 2：AI 识别摘要 ────────────────────────────────────────────

    def _build_section_ai(self):
        body = self._section_frame("AI 识别摘要", "点击「AI识图」获取商品识别结果")
        ai_frm = ttk.Frame(body)
        ai_frm.pack(fill=tk.X, pady=5)

        # 类型
        ttk.Label(ai_frm, text="商品类型：", width=12).grid(row=0, column=0, sticky=tk.W, pady=2)
        self._var_ai_type = tk.StringVar(); ttk.Entry(ai_frm, textvariable=self._var_ai_type, width=30).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        # 材质
        ttk.Label(ai_frm, text="主要材质：", width=12).grid(row=1, column=0, sticky=tk.W, pady=2)
        self._var_ai_material = tk.StringVar(); ttk.Entry(ai_frm, textvariable=self._var_ai_material, width=30).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        # 结构
        ttk.Label(ai_frm, text="商品结构：", width=12).grid(row=2, column=0, sticky=tk.W, pady=2)
        self._var_ai_structure = tk.StringVar(); ttk.Entry(ai_frm, textvariable=self._var_ai_structure, width=30).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)

        # 软硬/可折叠/可压缩/保形
        attr_frm = ttk.Frame(ai_frm)
        attr_frm.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=5)
        self._var_rigidity = tk.StringVar(value=""); self._var_foldable = tk.StringVar(value="")
        self._var_compressible = tk.StringVar(value=""); self._var_shapekeep = tk.StringVar(value="")
        for col, (label, var, options) in enumerate([
            ("软硬程度", self._var_rigidity, ["", "软", "中", "硬"]),
            ("可折叠性", self._var_foldable, ["", "好", "一般", "差"]),
            ("可压缩性", self._var_compressible, ["", "好", "一般", "差"]),
            ("是否保形", self._var_shapekeep, ["", "是", "否"]),
        ]):
            ttk.Label(attr_frm, text=label + "：", font=("", 8)).grid(row=0, column=col*2, padx=(0, 2))
            cb = ttk.Combobox(attr_frm, textvariable=var, values=options, state="readonly", width=6)
            cb.grid(row=0, column=col*2+1, padx=(0, 10), pady=2)

        # 简短说明
        ttk.Label(ai_frm, text="说明：", width=12).grid(row=4, column=0, sticky=tk.W, pady=2)
        self._var_ai_note = tk.StringVar(); ttk.Entry(ai_frm, textvariable=self._var_ai_note, width=46).grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)

        # 过期标记
        self._pkg_expired_var = tk.StringVar(value="")
        self._pkg_expired_lbl = ttk.Label(ai_frm, textvariable=self._pkg_expired_var, foreground="#cc6600", font=("", 8, "italic"))
        self._pkg_expired_lbl.grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=5)

        # 按钮行
        btn_row = ttk.Frame(ai_frm)
        btn_row.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        ttk.Button(btn_row, text="AI识图", command=self._ai_recognize).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_row, text="重新估算规格", command=self._reestimate_packaging).pack(side=tk.LEFT)
        ai_frm.columnconfigure(1, weight=1)
        # AI 属性变化 → 标记包装过期
        for ai_var in [self._var_rigidity, self._var_foldable, self._var_compressible, self._var_shapekeep]:
            ai_var.trace_add("write", lambda *_, v=ai_var: self._on_ai_attr_changed(v))

    def _on_ai_attr_changed(self, var_obj):
        if self._programmatic: return
        self._mark_packaging_expired()

    def _ai_recognize(self):
        """调用 Fake AI 识别图片，回填 AI 摘要和包装方案。"""
        paths = [s["path"] for s in self.image_states if s["path"] is not None]
        if not paths:
            messagebox.showinfo("提示", "请先上传至少一张图片。"); return
        try:
            self._ai_data = FakeVisionAdapter.recognize(paths)
        except Exception as exc:
            messagebox.showerror("AI识别失败", str(exc)); return
        # 回填 UI
        self._programmatic = True
        try:
            self._var_ai_type.set(self._ai_data.get("product_type", ""))
            self._var_ai_material.set(self._ai_data.get("material", ""))
            self._var_ai_structure.set(self._ai_data.get("structure", ""))
            self._var_rigidity.set(self._ai_data.get("rigidity", ""))
            self._var_foldable.set(self._ai_data.get("foldable", ""))
            self._var_compressible.set(self._ai_data.get("compressible", ""))
            self._var_shapekeep.set(self._ai_data.get("shape_keep", ""))
            self._var_ai_note.set(self._ai_data.get("note", ""))
        finally:
            self._programmatic = False
        # 更新包装规格显示
        self._update_packaging_display()
        self._clear_packaging_expired()
        # 不自动触发重新计算（等待用户选择货代后计算）

    def _reestimate_packaging(self):
        """重新估算包装规格（不重新调视觉API）。"""
        attrs = {
            "rigidity": self._var_rigidity.get().strip(),
            "foldable": self._var_foldable.get().strip(),
            "compressible": self._var_compressible.get().strip(),
            "shape_keep": self._var_shapekeep.get().strip(),
        }
        if not attrs["rigidity"]:
            messagebox.showinfo("提示", "请先执行「AI识图」或手动填写商品属性。"); return
        try:
            result = FakeVisionAdapter.reestimate_packaging(attrs)
        except Exception as exc:
            messagebox.showerror("重估失败", str(exc)); return
        # 合并到 _ai_data
        if not self._ai_data: self._ai_data = {}
        self._ai_data["normal"] = result.get("normal", {})
        self._ai_data["conservative"] = result.get("conservative", {})
        # 如果需要，更新 AI 摘要 note
        if result.get("note") and not self._var_ai_note.get().strip():
            self._var_ai_note.set(result.get("note", ""))
        self._update_packaging_display()
        # 更新裸件预填（如果为空）
        self._programmatic = True
        try:
            n = result.get("normal", {})
            if n and not self._var_net_w.get().strip():
                w = n.get("weight_g")
                if w: self._var_net_w.set(str(w))
            if n and not self._var_net_l.get().strip():
                self._var_net_l.set(str(n.get("length_cm", "")))
                self._var_net_wi.set(str(n.get("width_cm", "")))
                self._var_net_h.set(str(n.get("height_cm", "")))
        finally:
            self._programmatic = False
        self._clear_packaging_expired()

    def _update_packaging_display(self):
        """将 _ai_data 中的包装方案更新到 UI 双栏。

        统一数据结构：_pkg_normal / _pkg_conservative 始终包含
        length_cm, width_cm, height_cm, weight_g, method, note。
        """
        if not self._ai_data:
            return
        n = self._ai_data.get("normal", {})
        c = self._ai_data.get("conservative", {})
        if not hasattr(self, "_pkg_normal_widgets"): return
        # 正常档 — 统一字段
        self._pkg_normal = {
            "method": n.get("method", "—"),
            "length_cm": n.get("length_cm"),
            "width_cm": n.get("width_cm"),
            "height_cm": n.get("height_cm"),
            "weight_g": n.get("weight_g"),
            "note": n.get("note", "—"),
        }
        self._pkg_normal_widgets["method"].set(self._pkg_normal["method"])
        if self._pkg_normal["length_cm"] is not None:
            self._pkg_normal_widgets["dims"].set(
                f"{self._pkg_normal['length_cm']} × {self._pkg_normal['width_cm']} × {self._pkg_normal['height_cm']}")
        else:
            self._pkg_normal_widgets["dims"].set("—")
        wg = self._pkg_normal["weight_g"]
        self._pkg_normal_widgets["weight"].set(str(wg) if wg is not None else "—")
        self._pkg_normal_widgets["note"].set(self._pkg_normal["note"])
        # 保守档
        self._pkg_conservative = {
            "method": c.get("method", "—"),
            "length_cm": c.get("length_cm"),
            "width_cm": c.get("width_cm"),
            "height_cm": c.get("height_cm"),
            "weight_g": c.get("weight_g"),
            "note": c.get("note", "—"),
        }
        self._pkg_conservative_widgets["method"].set(self._pkg_conservative["method"])
        if self._pkg_conservative["length_cm"] is not None:
            self._pkg_conservative_widgets["dims"].set(
                f"{self._pkg_conservative['length_cm']} × {self._pkg_conservative['width_cm']} × {self._pkg_conservative['height_cm']}")
        else:
            self._pkg_conservative_widgets["dims"].set("—")
        wg = self._pkg_conservative["weight_g"]
        self._pkg_conservative_widgets["weight"].set(str(wg) if wg is not None else "—")
        self._pkg_conservative_widgets["note"].set(self._pkg_conservative["note"])

    def _packaging_display_on_switch(self):
        self._update_packaging_display()

    # ─── section 3：成本与裸件信息 ──────────────────────────────────────────

    def _build_section_cost_bare(self):
        body = self._section_frame("成本与裸件信息")
        self._body_cost_bare = body

        rf = ttk.Frame(body)
        rf.pack(fill=tk.X, pady=2)

        # 商品名称
        ttk.Label(rf, text="商品名称：").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self._var_name = tk.StringVar(); ttk.Entry(rf, textvariable=self._var_name, width=30).grid(row=0, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=2)

        for r, (label, name) in enumerate([
            ("商品成本（RMB）：", "cost"),
            ("国内运费/发往中转仓（RMB）：", "domestic"),
        ], start=1):
            ttk.Label(rf, text=label).grid(row=r, column=0, sticky=tk.W, padx=5, pady=2)
            var = tk.StringVar(); entry = tk.Entry(rf, textvariable=var, width=14, bg="white", relief="sunken")
            entry.grid(row=r, column=1, sticky=tk.EW, padx=5, pady=2)
            var.trace_add("write", lambda *_, n=name: self._validate_field(n))
            self._entry_vars[name] = var; self._entry_widgets[name] = entry

        # 裸件尺寸（一行）
        ttk.Label(rf, text="裸尺寸：长×宽×高 (cm)：").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self._var_net_l = tk.StringVar(); e_l = tk.Entry(rf, textvariable=self._var_net_l, width=6, bg="white", relief="sunken")
        e_l.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(rf, text="×").grid(row=3, column=2, sticky=tk.W)
        self._var_net_wi = tk.StringVar(); e_wi = tk.Entry(rf, textvariable=self._var_net_wi, width=6, bg="white", relief="sunken")
        e_wi.grid(row=3, column=2, padx=(15, 0), pady=2)
        ttk.Label(rf, text="×").grid(row=3, column=3, sticky=tk.W)
        self._var_net_h = tk.StringVar(); e_h = tk.Entry(rf, textvariable=self._var_net_h, width=6, bg="white", relief="sunken")
        e_h.grid(row=3, column=3, padx=(15, 0), pady=2)
        for n, var, e in [("net_l", self._var_net_l, e_l), ("net_wi", self._var_net_wi, e_wi), ("net_h", self._var_net_h, e_h)]:
            self._entry_vars[n] = var
            self._entry_widgets[n] = e
            var.trace_add("write", lambda *_, en=n: self._validate_field(en))

        # 裸重
        ttk.Label(rf, text="裸重 (g)：").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self._var_net_w = tk.StringVar(); e_w = tk.Entry(rf, textvariable=self._var_net_w, width=10, bg="white", relief="sunken")
        e_w.grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)
        self._entry_vars["net_w"] = self._var_net_w; self._entry_widgets["net_w"] = e_w
        self._var_net_w.trace_add("write", lambda *_, n="net_w": self._validate_field(n))

        rf.columnconfigure(1, weight=1)

    # ─── section 4：正常/保守包装档 ────────────────────────────────────────

    def _build_section_packaging(self):
        body = self._section_frame("包装规格", "正常档与保守档同时展示")
        dual = ttk.Frame(body)
        dual.pack(fill=tk.X, pady=5)

        # 正常档
        nf = ttk.LabelFrame(dual, text="正常档（默认采用）")
        nf.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._pkg_normal_widgets = {}
        for r, (label, key) in enumerate([
            ("包装方式：", "method"), ("长×宽×高 (cm)：", "dims"),
            ("包装后重量 (g)：", "weight"), ("说明：", "note"),
        ]):
            ttk.Label(nf, text=label, font=("", 8)).grid(row=r, column=0, sticky=tk.W, padx=3, pady=1)
            var = tk.StringVar(value="待估算"); lbl = ttk.Label(nf, textvariable=var, font=("", 9, "bold"), foreground="#2a6496")
            lbl.grid(row=r, column=1, sticky=tk.W, padx=3, pady=1)
            self._pkg_normal_widgets[key] = var

        # 保守档
        cf = ttk.LabelFrame(dual, text="保守档")
        cf.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._pkg_conservative_widgets = {}
        for r, (label, key) in enumerate([
            ("包装方式：", "method"), ("长×宽×高 (cm)：", "dims"),
            ("包装后重量 (g)：", "weight"), ("说明：", "note"),
        ]):
            ttk.Label(cf, text=label, font=("", 8)).grid(row=r, column=0, sticky=tk.W, padx=3, pady=1)
            var = tk.StringVar(value="待估算"); lbl = ttk.Label(cf, textvariable=var, font=("", 9, "bold"), foreground="#994d00")
            lbl.grid(row=r, column=1, sticky=tk.W, padx=3, pady=1)
            self._pkg_conservative_widgets[key] = var

        dual.columnconfigure(0, weight=1); dual.columnconfigure(1, weight=1)

        # 切换档位
        switch = ttk.Frame(body)
        switch.pack(anchor=tk.W, pady=(5, 0))
        self._mode_var = tk.StringVar(value="normal")
        ttk.Radiobutton(switch, text="采用正常档", variable=self._mode_var, value="normal",
                        command=self._switch_packaging_mode).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(switch, text="采用保守档", variable=self._mode_var, value="conservative",
                        command=self._switch_packaging_mode).pack(side=tk.LEFT)

    def _switch_packaging_mode(self):
        self._packaging_mode = self._mode_var.get()
        self._update_packaging_display()
        self.recalculate()

    # ─── section 5：货代方案 ────────────────────────────────────────────────

    def _build_section_forwarders(self):
        body = self._section_frame("货代方案", "选择本次发货采用的货代")
        ff = ttk.Frame(body)
        ff.pack(fill=tk.X, pady=5)
        ttk.Label(ff, text="当前采用货代：").pack(side=tk.LEFT, padx=(5, 5))
        self._forwarder_var = tk.StringVar(value="")
        self._forwarder_combo = ttk.Combobox(ff, textvariable=self._forwarder_var, values=[""], state="readonly", width=14)
        self._forwarder_combo.pack(side=tk.LEFT, padx=5)
        self._forwarder_combo.bind("<<ComboboxSelected>>", lambda e: self._on_forwarder_changed())
        self._refresh_route_choices()

        # 货代卡片区域
        self._fwd_cards = ttk.Frame(body)
        self._fwd_cards.pack(fill=tk.X, pady=5)
        ttk.Label(self._fwd_cards, text="加载货代卡片...", foreground="#888").pack()

    # ─── section 6：系统总成本 ──────────────────────────────────────────────

    def _build_section_total_cost(self):
        body = self._section_frame("系统总成本", "只读 / 当前计算结果")
        self._summary_vars = {}
        items = [
            ("当前包装档：", "mode"),
            ("当前货代：", "forwarder"),
            ("商品成本：", "cost_summary"),
            ("国内运费：", "domestic_summary"),
            ("物流费用：", "logistics_summary"),
            ("当前系统总成本：", "total_summary"),
        ]
        for r, (label, key) in enumerate(items):
            ttk.Label(body, text=label, font=("", 9)).grid(row=r, column=0, sticky=tk.W, padx=5, pady=1)
            var = tk.StringVar(value="—")
            ttk.Label(body, textvariable=var, font=("", 10, "bold"), foreground="#333").grid(row=r, column=1, sticky=tk.W, padx=5, pady=1)
            self._summary_vars[key] = var

    # ─── section 7：利润测算 ────────────────────────────────────────────────

    def _build_section_profit(self):
        body = self._section_frame("利润测算", "售价/利润/利润率可双向联动")
        pf = ttk.Frame(body)
        pf.pack(fill=tk.X, pady=5)

        for r, (label, name, tip) in enumerate([
            ("SHEIN 二次核价 ($)：", "shein", "手动输入"),
            ("实际售价 (RMB)：", "price_rmb", "可编辑"),
            ("实际售价 ($)：", "price_usd", "联动换算"),
            ("降价预留 (%)：", "promo_rate", ""),
            ("目标利润 (元)：", "target_profit", "改此项反推售价"),
            ("目标净利率 (%)：", "target_rate", "改此项反推售价"),
        ]):
            ttk.Label(pf, text=label).grid(row=r, column=0, sticky=tk.W, padx=5, pady=2)
            var = tk.StringVar()
            entry = tk.Entry(pf, textvariable=var, width=14, bg="white", relief="sunken")
            entry.grid(row=r, column=1, sticky=tk.W, padx=5, pady=2)
            if name == "shein":
                ttk.Label(pf, text="（仅支持手动输入）", foreground="#888", font=("", 8)).grid(row=r, column=2, sticky=tk.W)
            var.trace_add("write", lambda *_, n=name: self._validate_field(n) if n in ("target_rate", "promo_rate") else None)
            self._entry_vars[name] = var; self._entry_widgets[name] = entry

        # 尾程费用（可配置）
        ttk.Label(pf, text="尾程费用 (元)：").grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)
        self._var_tail_haul = tk.StringVar(value=str(self._cfg.default_tail_haul))
        e_tail = tk.Entry(pf, textvariable=self._var_tail_haul, width=14, bg="white", relief="sunken")
        e_tail.grid(row=6, column=1, sticky=tk.W, padx=5, pady=2)
        self._entry_vars["tail"] = self._var_tail_haul; self._entry_widgets["tail"] = e_tail

        # 利润调整规则
        pr = ttk.Frame(pf)
        pr.grid(row=7, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        ttk.Label(pr, text="利润调整规则：").pack(side=tk.LEFT)
        self._profit_rule_var = tk.StringVar(value="无")
        self._profit_rule_combo = ttk.Combobox(pr, textvariable=self._profit_rule_var, state="readonly", width=24)
        self._profit_rule_combo.pack(side=tk.LEFT, padx=5)
        self._profit_rule_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_profit_rule_changed())
        self._refresh_profit_rule_choices()

        # 只读结果条
        sep = ttk.Separator(pf, orient=tk.HORIZONTAL)
        sep.grid(row=8, column=0, columnspan=3, sticky=tk.EW, pady=(8, 5))
        ttk.Label(pf, text="计算结果（只读）", font=("", 9, "bold")).grid(row=9, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0, 3))
        self._result_labels = {}
        self._result_widgets = {}
        for rr, (key, label) in enumerate([
            ("vol_weight", "体积重 (kg)："), ("charge_weight", "计费重量 (kg)："),
            ("head_haul", "头程费用 (元)："), ("total_logistics", "物流总费用 (元)："),
            ("total_cost", "系统总成本 (元)："), ("profit", "净利润 (元)："),
            ("profit_rate", "净利率 (%)："), ("suggested_price", "建议售价 (RMB)："),
            ("converted_usd", "折合美元 ($)："),
        ], start=10):
            ttk.Label(pf, text=label, font=("", 8)).grid(row=rr, column=0, sticky=tk.W, padx=5, pady=1)
            var = tk.StringVar(value="—"); lbl = ttk.Label(pf, textvariable=var, font=("", 10, "bold"), foreground="#1a5276")
            lbl.grid(row=rr, column=1, columnspan=2, sticky=tk.W, padx=5, pady=1)
            self._result_labels[key] = var
            self._result_widgets[key] = lbl

        self._profit_adjustment_var = tk.StringVar(value="未选择规则")
        ttk.Label(pf, textvariable=self._profit_adjustment_var, foreground="#336699", font=("", 8), wraplength=400).grid(
            row=19, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)

        # 汇率提示
        self._rate_notice_var = tk.StringVar()
        self._rate_notice_label = ttk.Label(pf, textvariable=self._rate_notice_var, foreground="#cc6600", font=("", 8, "italic"), wraplength=400)
        self._rate_notice_label.grid(row=20, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        for n in ["cost","domestic","net_w","net_l","net_wi","net_h",
                  "pkg_w","pkg_l","pkg_wi","pkg_h","tail","shein"]:
            if n in self._entry_vars: self._entry_vars[n].trace_add("write", lambda *_, x=n: self._on_field_changed(x))
        for n in ["price_rmb","price_usd","target_rate","target_profit","promo_rate"]:
            if n in self._entry_vars: self._entry_vars[n].trace_add("write", lambda *_, x=n: self._on_field_changed(x))

    # ─── section 8：底部 ────────────────────────────────────────────────────

    def _build_section_bottom(self):
        sep2 = ttk.Separator(self._main_frame, orient=tk.HORIZONTAL)
        sep2.pack(fill=tk.X, padx=10, pady=(5, 0))
        btn_frame = ttk.Frame(self._main_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="保存本次记录", command=self.save_product, width=16).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="清空并新建", command=self._clear_and_new, width=16).pack(side=tk.LEFT)
        # restore_product 和 _force_recalc 保留为内部方法，不在底部显示按钮

    # ─── 包装档过期 ────────────────────────────────────────────────────────

    def _mark_packaging_expired(self):
        if not hasattr(self, "_pkg_expired_var"): return
        self._packaging_expired = True
        self._pkg_expired_var.set("⚠ 包装规格已过期 — 请修改上游信息后点击「重新估算规格」")
        if hasattr(self, "_pkg_expired_lbl"):
            self._pkg_expired_lbl.configure(foreground="#cc6600")

    def _clear_packaging_expired(self):
        if not hasattr(self, "_pkg_expired_var"): return
        self._packaging_expired = False
        self._pkg_expired_var.set("")
        if hasattr(self, "_pkg_expired_lbl"):
            self._pkg_expired_lbl.configure(foreground="#cc6600")

    # ─── 校验 ──────────────────────────────────────────────────────────────

    def _validate_field(self, name):
        entry = self._entry_widgets.get(name); var = self._entry_vars.get(name)
        if not entry or not var: return
        val = var.get().strip()
        if val == "": entry.configure(bg="white"); return
        ok = _is_valid_rate(val) if name in ("target_rate","promo_rate") else _is_valid_number(val)
        entry.configure(bg="white" if ok else "#ffcccc")

    def _has_any_invalid(self):
        for name in self._entry_vars:
            val = self._entry_vars[name].get().strip()
            if val == "": continue
            ok = _is_valid_rate(val) if name in ("target_rate","promo_rate") else _is_valid_number(val)
            if not ok: return True
        tr = _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get())
        pr = _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get())
        if tr is not None and pr is not None and (tr + pr) >= 100: return True
        return False

    def _get_invalid_list(self):
        inv = []
        num_fields = [("cost","商品成本"),("domestic","发往中转仓运费"),
            ("net_w","裸重"),("net_l","裸长"),("net_wi","裸宽"),("net_h","裸高"),
            ("tail","尾程费用"),("shein","SHEIN二次核价"),("price_rmb","售价人民币"),("price_usd","售价美元")]
        for n, lb in num_fields:
            if n in self._entry_vars:
                v = self._entry_vars[n].get().strip()
                if v != "" and not _is_valid_number(v): inv.append(f"{lb}(非法)")
        for n, lb in [("target_rate","目标净利率"),("promo_rate","推广预留比例")]:
            if n in self._entry_vars:
                v = self._entry_vars[n].get().strip()
                if v != "" and not _is_valid_rate(v): inv.append(f"{lb}(非法)")
        tr = _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get())
        pr = _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get())
        if tr is not None and pr is not None and (tr + pr) >= 100: inv.append(f"净利率+推广≥100%（{tr+pr:.0f}%）")
        return inv

    # ─── 事件 ──────────────────────────────────────────────────────────────

    def _on_field_changed(self, field_type):
        if self._programmatic: return
        if field_type in ("net_w",) and self._weight_unit_version == "legacy_unknown":
            self._weight_confirmed = True
        if field_type in ("price_rmb","price_usd","target_profit"):
            self._calc_direction = "price"; self._last_modified = field_type
        elif field_type == "target_rate":
            self._calc_direction = "rate"
        # 上游属性变化 → 标记包装过期
        if field_type in ("net_l", "net_wi", "net_h", "net_w") and not self._programmatic:
            self._mark_packaging_expired()
        # AI 属性编辑也触发过期
        for attr_var in [self._var_rigidity, self._var_foldable, self._var_compressible, self._var_shapekeep]:
            pass  # 在 Step 3 绑定
        self.recalculate()

    def _on_forwarder_changed(self):
        if self._programmatic: return
        self._saved_rule_context = None; self._show_rate_banner = False
        self._show_rate_notice(None); self.recalculate()

    def _on_profit_rule_changed(self):
        if not self._programmatic:
            self._profit_rule_explicitly_changed = True
            self._profit_rule_source = "none" if self._profit_rule_var.get() == "无" else "current"
            self._saved_profit_rule = None
            self._profit_rule_unavailable_notice = False
            self.recalculate()

    def recalculate(self):
        if self._programmatic: return
        self._programmatic = True
        try:
            if self._has_any_invalid():
                for k in self._result_labels: self._result_labels[k].set("输入错误")
                self._computed = {}
            else:
                self._do_recalculate()
        finally: self._programmatic = False

    # ─── OCR 入口（保留兼容，不再推荐使用）─────────────────────────────────

    def _open_ocr_intake(self):
        factory = self._ocr_dialog_factory or self._default_ocr_dialog
        root = self.winfo_toplevel()
        dlg = factory(root, self._ocr_controller)
        if isinstance(dlg, tk.Toplevel):
            root.wait_window(dlg)
        result = getattr(dlg, "result", None)
        if result is None:
            return
        self._apply_ocr_selections(result)

    def _default_ocr_dialog(self, parent, controller):
        from ui.ocr_intake_dialog import OcrIntakeDialog
        return OcrIntakeDialog(parent, controller=controller)

    def _apply_ocr_selections(self, selections):
        price_map = {"shein_price_usd": "shein", "product_cost_rmb": "cost", "domestic_shipping_rmb": "domestic"}
        dim_map = {"weight_g": "net_w", "length_cm": "net_l", "width_cm": "net_wi", "height_cm": "net_h"}
        self._programmatic = True
        try:
            for field_name, sel in selections.items():
                if sel.confirmed_value is None: continue
                value = sel.confirmed_value
                if field_name in price_map:
                    self._entry_vars[price_map[field_name]].set(_fmt(value))
                elif field_name in dim_map:
                    if sel.measurement_scope == MeasurementScope.BARE:
                        self._entry_vars[dim_map[field_name]].set(_fmt(value))
        finally:
            self._programmatic = False
        self.recalculate()

    def _force_recalc(self):
        self._saved_rule_context = None; self._show_rate_banner = False; self._show_rate_notice(None)
        if self._profit_rule_source == "frozen" and self._saved_profit_rule:
            current = self._cfg.get_profit_adjustment_rule(self._saved_profit_rule.get("rule_id"))
            if current and current.get("is_enabled") and not current.get("is_archived"):
                self._profit_rule_source = "current"; self._saved_profit_rule = None
                self._set_profit_rule_id(current["rule_id"])
            else:
                self._profit_rule_source = "none"; self._saved_profit_rule = None
                self._set_profit_rule_id(None)
                self._profit_rule_unavailable_notice = True
                messagebox.showwarning("当前规则不可用", "原冻结规则当前已停用、归档或不存在，无法使用当前版本；已切换为「无规则」。")
        self._programmatic = True
        try: self._entry_vars["tail"].set(str(self._cfg.default_tail_haul))
        finally: self._programmatic = False
        self.recalculate()

    # ─── 计算核心（保留原有逻辑）────────────────────────────────────────────

    def _do_recalculate(self):
        ctx = self._get_active_rule_context()
        cost = _safe_float(self._entry_vars.get("cost", tk.StringVar()).get())
        domestic = _safe_float(self._entry_vars.get("domestic", tk.StringVar()).get())

        # 包装数据 — 根据当前采用档选正常/保守（统一字段 length_cm/width_cm/height_cm/weight_g）
        pkg_w = pkg_l = pkg_wi = pkg_h = None
        active_pkg = self._pkg_conservative if self._packaging_mode == "conservative" else self._pkg_normal
        if active_pkg and active_pkg.get("length_cm") is not None:
            pkg_l = _safe_float(active_pkg.get("length_cm"))
            pkg_wi = _safe_float(active_pkg.get("width_cm"))
            pkg_h = _safe_float(active_pkg.get("height_cm"))
            pkg_w = _safe_float(active_pkg.get("weight_g"))
        else:
            # fallback — manual input (legacy fields)
            pkg_w = _safe_float(self._entry_vars.get("pkg_w", tk.StringVar()).get() if "pkg_w" in self._entry_vars else None)
            pkg_l = _safe_float(self._entry_vars.get("pkg_l", tk.StringVar()).get() if "pkg_l" in self._entry_vars else None)
            pkg_wi = _safe_float(self._entry_vars.get("pkg_wi", tk.StringVar()).get() if "pkg_wi" in self._entry_vars else None)
            pkg_h = _safe_float(self._entry_vars.get("pkg_h", tk.StringVar()).get() if "pkg_h" in self._entry_vars else None)

        tail_haul = _safe_float(self._entry_vars.get("tail", tk.StringVar()).get())
        price_rmb = _safe_float(self._entry_vars.get("price_rmb", tk.StringVar()).get())
        target_rate = _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get())
        promo_rate = _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get())

        # 公斤换算
        actual_weight_kg = pkg_w / 1000.0 if pkg_w is not None else None
        head_rate = ctx.get("head_haul_rate")
        fixed_fee = ctx.get("fixed_service_fee")
        exchange_rate = ctx.get("exchange_rate")
        forwarder = ctx.get("forwarder")
        volume_divisor = ctx.get("volume_divisor")

        self._computed = {
            "forwarder": forwarder, "head_haul_rate": head_rate,
            "fixed_service_fee": fixed_fee, "tail_haul_cost": tail_haul,
            "exchange_rate": exchange_rate, "volume_divisor": volume_divisor,
            "rule_version": ctx.get("rule_version"),
            "calculation_schema_version": CALCULATION_SCHEMA_VERSION,
        }

        if forwarder is None or head_rate is None or fixed_fee is None:
            for k in self._result_labels: self._result_labels[k].set("请选择货代" if k == "head_haul" else "—")
            for k in self._summary_vars: self._summary_vars[k].set("—")
            self._computed.update({"head_haul": None, "total_logistics": None, "total_cost": None,
                                    "profit": None, "profit_rate": None, "suggested_price": None,
                                    "volumetric_weight": None, "chargeable_weight": None, "converted_usd": None})
            return

        # USD→RMB 联动
        if self._last_modified == "price_usd":
            pu = _safe_float(self._entry_vars.get("price_usd", tk.StringVar()).get())
            if pu is not None and exchange_rate is not None and exchange_rate > 0:
                price_rmb = pu * exchange_rate
                self._entry_vars.get("price_rmb", tk.StringVar()).set(f"{price_rmb:.2f}")
                self._last_modified = "price_rmb"

        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h, volume_divisor)
        chg_w = chargeable_weight(actual_weight_kg, vol_w)
        head_cost = head_haul_cost(chg_w, head_rate)
        head_partial = (head_cost is None)

        fwd_label = ctx.get("route_display_name") or self._cfg.get_forwarder_label(forwarder)
        self._set_result("vol_weight", vol_w, " kg")
        self._set_result("charge_weight", chg_w, " kg")
        self._set_result("head_haul", head_cost, f" 元({fwd_label})" if head_cost is not None else "", partial=head_partial)

        logistics = total_logistics_cost(head_cost, fixed_fee, tail_haul) if not head_partial else None
        if head_partial:
            known_log = known_logistics_subtotal(head_cost, fixed_fee, tail_haul)
            self._set_result("total_logistics", known_log if known_log > 0 else None, " 元", partial=True)
        else:
            self._set_result("total_logistics", logistics, " 元")

        tc = total_cost(cost, domestic, logistics) if logistics is not None else None
        if tc is None and logistics is None:
            known_tc = known_total_cost_subtotal(cost, domestic, known_logistics_subtotal(head_cost, fixed_fee, tail_haul))
            self._set_result("total_cost", known_tc if known_tc > 0 else None, " 元", partial=True)
        else:
            self._set_result("total_cost", tc, " 元")

        self._computed["head_haul"] = head_cost
        self._computed["total_logistics"] = logistics
        self._computed["total_cost"] = tc
        self._computed["volumetric_weight"] = vol_w
        self._computed["chargeable_weight"] = chg_w
        self._computed["actual_weight_g"] = pkg_w
        self._computed["actual_weight_kg"] = actual_weight_kg

        # 系统总成本摘要
        mode_label = "正常档" if self._packaging_mode == "normal" else "保守档"
        if hasattr(self, "_summary_vars"):
            self._summary_vars["mode"].set(mode_label)
            self._summary_vars["forwarder"].set(fwd_label or "未选择")
            self._summary_vars["cost_summary"].set(f"{cost:.2f} 元" if cost is not None else "—")
            self._summary_vars["domestic_summary"].set(f"{domestic:.2f} 元" if domestic is not None else "—")
            self._summary_vars["logistics_summary"].set(f"{logistics:.2f} 元" if logistics is not None else "数据不足")
            self._summary_vars["total_summary"].set(f"{tc:.2f} 元" if tc is not None else "待补充")

        if head_partial or logistics is None or tc is None:
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
            self._set_result("suggested_price", None)
            self._set_result("converted_usd", None)
            self._computed.update({"profit": None, "profit_rate": None, "suggested_price": None, "converted_usd": None})
            return

        p_rate = promo_rate if promo_rate is not None else 0

        # 目标利润反推
        target_profit = _safe_float(self._entry_vars.get("target_profit", tk.StringVar()).get())
        if self._last_modified == "target_profit" and target_profit is not None:
            sp = tc + target_profit / (1 - p_rate / 100) if p_rate < 100 else None
            self._set_result("suggested_price", sp, " 元")
            self._computed["suggested_price"] = sp
            converted = rmb_to_usd(sp, exchange_rate) if sp is not None else None
            self._set_result("converted_usd", converted, " $")
            self._computed["converted_usd"] = converted
            if sp is not None:
                np = target_profit; npr = np / sp * 100 if sp > 0 else None
                np, npr = self._apply_profit_adjustment(np, sp, exchange_rate, logistics)
                self._set_result("profit", np, " 元"); self._set_result("profit_rate", npr, " %")
                self._computed["profit"] = np; self._computed["profit_rate"] = npr
                self._entry_vars["price_rmb"].set(_fmt(sp))
            else:
                self._set_result("profit", None); self._set_result("profit_rate", None)
                self._computed["profit"] = None; self._computed["profit_rate"] = None
        elif self._calc_direction == "rate" and target_rate is not None:
            if (target_rate + p_rate) >= 100:
                self._set_result("suggested_price", None, suffix=" (利润率+推广≥100%)")
                self._set_result("profit", None); self._set_result("profit_rate", None)
                self._computed.update({"suggested_price": None, "profit": None, "profit_rate": None})
            else:
                sp = suggested_price_from_rate(tc, target_rate, promo_rate or 0)
                self._set_result("suggested_price", sp, " 元"); self._computed["suggested_price"] = sp
                converted = rmb_to_usd(sp, exchange_rate) if sp is not None else None
                self._set_result("converted_usd", converted, " $"); self._computed["converted_usd"] = converted
                if price_rmb is not None and price_rmb > 0:
                    np = net_profit_amount(price_rmb, tc, p_rate)
                    np, npr = self._apply_profit_adjustment(np, price_rmb, exchange_rate, logistics)
                    self._set_result("profit", np, " 元"); self._set_result("profit_rate", npr, " %")
                    self._computed["profit"] = np; self._computed["profit_rate"] = npr
                    u = rmb_to_usd(price_rmb, exchange_rate)
                    if u is not None: self._entry_vars["price_usd"].set(f"{u:.2f}")
                else:
                    self._set_result("profit", None); self._set_result("profit_rate", None)
                    self._computed["profit"] = None; self._computed["profit_rate"] = None
        else:
            if price_rmb is not None and price_rmb > 0:
                np = net_profit_amount(price_rmb, tc, p_rate)
                np, npr = self._apply_profit_adjustment(np, price_rmb, exchange_rate, logistics)
                self._set_result("profit", np, " 元"); self._set_result("profit_rate", npr, " %")
                self._computed["profit"] = np; self._computed["profit_rate"] = npr
                u = rmb_to_usd(price_rmb, exchange_rate)
                self._set_result("converted_usd", u, " $"); self._computed["converted_usd"] = u
                if u is not None: self._entry_vars["price_usd"].set(f"{u:.2f}")
            else:
                self._set_result("profit", None); self._set_result("profit_rate", None)
                self._set_result("converted_usd", None, " $")
                self._computed["profit"] = None; self._computed["profit_rate"] = None
                self._computed["converted_usd"] = None
            self._set_result("suggested_price", None)
            self._computed["suggested_price"] = None

    def _set_result(self, key, value, suffix="", partial=False):
        var = self._result_labels.get(key)
        if not var: return
        if value is None:
            if partial: var.set("数据不足(物流费用不完整)")
            elif suffix: var.set(f"数据不足{suffix}")
            else: var.set("数据不足")
        elif partial: var.set(f"≥{value:.2f}{suffix}(估算)")
        else: var.set(f"{value:.2f}{suffix}")

    def _apply_profit_adjustment(self, base_profit, price_rmb, exchange_rate, logistics):
        rule = self._saved_profit_rule if self._profit_rule_source == "frozen" else None
        rule_id = self._get_profit_rule_id()
        if rule is None and self._profit_rule_source == "current":
            rule = self._cfg.get_profit_adjustment_rule(rule_id) if rule_id else None
        price_var = self._entry_vars.get("price_usd")
        price_usd = _safe_float(price_var.get()) if price_var is not None else None
        if price_usd is None:
            price_usd = rmb_to_usd(price_rmb, exchange_rate)
        cost_var = self._entry_vars.get("cost")
        result = evaluate_rule(rule, {"final_price_usd": price_usd, "final_price_rmb": price_rmb,
                                      "product_cost_rmb": _safe_float(cost_var.get()) if cost_var is not None else None,
                                      "logistics_cost_rmb": logistics}, exchange_rate)
        snapshot = dict(rule) if rule else None
        self._computed["profit_adjustment"] = {"rule": snapshot, **result}
        self._computed["profit_before_adjustment"] = base_profit
        adjusted = base_profit + result.get("adjustment_rmb", 0.0) if base_profit is not None else None
        rate = adjusted / price_rmb * 100 if adjusted is not None and price_rmb and price_rmb > 0 else None
        if not rule:
            msg = "无规则（原冻结规则当前已停用、归档或不存在）" if getattr(self, "_profit_rule_unavailable_notice", False) else "无规则"
            self._profit_adjustment_var.set(msg)
        else:
            prefix = "历史冻结规则" if self._profit_rule_source == "frozen" else "当前规则"
            sign = "+" if result.get("adjustment_rmb", 0) >= 0 else ""
            self._profit_adjustment_var.set(f"{prefix}：{rule['display_name']}\n调整：{result.get('amount_original', 0):.2f} {result.get('currency') or rule.get('currency')}（{sign}{result.get('adjustment_rmb', 0):.2f} RMB）")
        return adjusted, rate

    def _show_rate_notice(self, diffs):
        if diffs:
            lines = [f"{k} {v[0]}→{v[1]}" for k, v in diffs.items()]
            self._rate_notice_var.set("费率已变更: " + ", ".join(lines) + " | 点「用当前规则重算」更新")
            self._rate_notice_label.grid()
        else:
            self._rate_notice_var.set(""); self._rate_notice_label.grid_remove()

    # ─── 按钮 ──────────────────────────────────────────────────────────────

    def _get_forwarder_key(self):
        return self._route_display_to_key.get(self._forwarder_var.get())

    def _set_forwarder_key(self, key):
        route = self._cfg.get_route_rates(key) if key and hasattr(self._cfg, "get_route_rates") else None
        self._forwarder_var.set((route or {}).get("display_name") or FORWARDER_LABELS.get(key, ""))

    def _refresh_route_choices(self):
        routes = self._cfg.get_enabled_routes()
        self._route_display_to_key = {r["display_name"]: r["route_id"] for r in routes}
        if hasattr(self, "_forwarder_combo"):
            self._forwarder_combo["values"] = [""] + list(self._route_display_to_key)

    def _get_profit_rule_id(self):
        var = getattr(self, "_profit_rule_var", None)
        return self._profit_rule_display_to_id.get(var.get()) if var is not None else None

    def _set_profit_rule_id(self, rule_id):
        if not hasattr(self, "_profit_rule_var"): return
        rule = self._cfg.get_profit_adjustment_rule(rule_id) if rule_id else None
        self._profit_rule_var.set((rule or {}).get("display_name") or "无")

    def _refresh_profit_rule_choices(self):
        profit_rule_var = getattr(self, "_profit_rule_var", None)
        selected = profit_rule_var.get() if profit_rule_var is not None else "无"
        rules = self._cfg.get_enabled_profit_adjustment_rules()
        self._profit_rule_display_to_id = {rule["display_name"]: rule["rule_id"] for rule in rules}
        if hasattr(self, "_profit_rule_combo"):
            self._profit_rule_combo["values"] = ["无"] + list(self._profit_rule_display_to_id)
        if self._profit_rule_source != "frozen" and selected not in self._profit_rule_display_to_id:
            self._profit_rule_var.set("无")

    def new_product(self):
        self._product_id = None; self._has_snapshot = False
        self._calc_direction = None; self._last_modified = None
        self._saved_rule_context = None; self._show_rate_banner = False
        self._saved_profit_rule = None; self._profit_rule_source = "none"
        self._profit_rule_explicitly_changed = False; self._profit_rule_unavailable_notice = False
        self._ai_data = {}; self._packaging_mode = "normal"; self._packaging_expired = False
        self._pkg_normal = {}; self._pkg_conservative = {}
        # 清空图片
        if hasattr(self, "image_states"):
            for s in self.image_states:
                s["path"] = None; s["photo"] = None
                try:
                    s["label"].configure(image="", text="点击上传\n或拖入图片\n或 Ctrl+V", foreground="#999", compound=tk.CENTER)
                except Exception: pass
        self._show_rate_notice(None); self._forwarder_var.set(""); self.clear_form()
        self._reset_profit_adjustment_display()

    def _reset_profit_adjustment_display(self):
        if hasattr(self, "_profit_adjustment_var") and self._profit_adjustment_var is not None:
            self._profit_adjustment_var.set("未选择规则")

    def clear_form(self):
        self._product_id = None; self._has_snapshot = False
        self._saved_rule_context = None; self._show_rate_banner = False
        self._calc_direction = None; self._last_modified = None; self._show_rate_notice(None)
        self._reset_profit_adjustment_display()
        self._ai_data = {}; self._packaging_mode = "normal"; self._packaging_expired = False
        self._pkg_normal = {}; self._pkg_conservative = {}
        self._clear_packaging_expired()
        self._programmatic = True
        try:
            for n, v in self._entry_vars.items():
                v.set(str(self._cfg.default_tail_haul) if n == "tail" else "")
            self._var_name.set(""); self._forwarder_var.set("")
            if hasattr(self, "_var_ai_type"): self._var_ai_type.set(""); self._var_ai_material.set(""); self._var_ai_structure.set("")
            if hasattr(self, "_var_ai_note"): self._var_ai_note.set(""); self._var_rigidity.set("")
            if hasattr(self, "_var_foldable"): self._var_foldable.set(""); self._var_compressible.set(""); self._var_shapekeep.set("")
            if hasattr(self, "_profit_rule_var"): self._profit_rule_var.set("无")
            self._saved_profit_rule = None; self._profit_rule_source = "none"
            self._profit_rule_explicitly_changed = False; self._profit_rule_unavailable_notice = False
            for k in self._result_labels: self._result_labels[k].set("—")
            if hasattr(self, "_summary_vars"):
                for k in self._summary_vars: self._summary_vars[k].set("—")
            for w in list(getattr(self, "_pkg_normal_widgets", {}).values()) + list(getattr(self, "_pkg_conservative_widgets", {}).values()):
                w.set("待估算")
            self._computed = {}
        finally: self._programmatic = False

    def _clear_and_new(self):
        # 检查未保存修改
        if self._product_id is not None or any(
            v.get().strip() != "" for v in self._entry_vars.values() if v.get().strip() not in ("", str(self._cfg.default_tail_haul))
        ) or self._var_name.get().strip() != "":
            if not messagebox.askyesno("确认清空", "当前页面存在未保存内容。确定清空并新建吗？"):
                return
        self.new_product()

    # ─── 保存 / 加载（保留原有逻辑）─────────────────────────────────────────

    def _gather_data(self):
        return {
            "name": self._var_name.get().strip(),
            "cost": _safe_float(self._entry_vars.get("cost", tk.StringVar()).get()),
            "domestic_shipping": _safe_float(self._entry_vars.get("domestic", tk.StringVar()).get()),
            "net_weight": _safe_float(self._entry_vars.get("net_w", tk.StringVar()).get()),
            "net_length": _safe_float(self._entry_vars.get("net_l", tk.StringVar()).get()),
            "net_width": _safe_float(self._entry_vars.get("net_wi", tk.StringVar()).get()),
            "net_height": _safe_float(self._entry_vars.get("net_h", tk.StringVar()).get()),
            # packaging fallback fields
            "packaged_weight": _safe_float(self._entry_vars.get("pkg_w", tk.StringVar()).get()) if "pkg_w" in self._entry_vars else None,
            "packaged_length": _safe_float(self._entry_vars.get("pkg_l", tk.StringVar()).get()) if "pkg_l" in self._entry_vars else None,
            "packaged_width": _safe_float(self._entry_vars.get("pkg_wi", tk.StringVar()).get()) if "pkg_wi" in self._entry_vars else None,
            "packaged_height": _safe_float(self._entry_vars.get("pkg_h", tk.StringVar()).get()) if "pkg_h" in self._entry_vars else None,
            "tail_haul_cost": _safe_float(self._entry_vars.get("tail", tk.StringVar()).get()),
            "shein_price_usd": _safe_float(self._entry_vars.get("shein", tk.StringVar()).get()),
            "price_rmb": _safe_float(self._entry_vars.get("price_rmb", tk.StringVar()).get()),
            "price_usd": _safe_float(self._entry_vars.get("price_usd", tk.StringVar()).get()),
            "target_profit_rate": _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get()),
            "promo_rate": _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get()),
            "notes": "",
            "freight_forwarder": self._computed.get("forwarder"),
            "fixed_service_fee": self._computed.get("fixed_service_fee"),
        }

    def _build_rule_snapshot(self):
        return {
            "route_id": self._computed.get("forwarder"),
            "route_key": self._computed.get("forwarder"),
            "route_display_name": (
                self._cfg.get_forwarder_label(self._computed.get("forwarder"))
                if hasattr(self, "_cfg") and hasattr(self._cfg, "get_forwarder_label")
                else FORWARDER_LABELS.get(self._computed.get("forwarder"))
            ),
            "exchange_rate": self._computed.get("exchange_rate"),
            "head_haul_rate": self._computed.get("head_haul_rate"),
            "fixed_service_fee": self._computed.get("fixed_service_fee"),
            "tail_haul_cost": self._computed.get("tail_haul_cost"),
            "volume_divisor": self._computed.get("volume_divisor"),
            "forwarder": self._computed.get("forwarder"),
            "rule_version": self._computed.get("rule_version"),
            "weight_unit": getattr(self, "_weight_unit_version", "g_v1"),
            "profit_adjustment": self._computed.get("profit_adjustment"),
        }

    def _build_calculation_snapshot(self):
        return {
            "calculation_schema_version": CALCULATION_SCHEMA_VERSION,
            "volumetric_weight": self._computed.get("volumetric_weight"),
            "actual_weight_g": self._computed.get("actual_weight_g"),
            "actual_weight_kg": self._computed.get("actual_weight_kg"),
            "chargeable_weight": self._computed.get("chargeable_weight"),
            "head_haul_cost": self._computed.get("head_haul"),
            "total_logistics_cost": self._computed.get("total_logistics"),
            "total_cost": self._computed.get("total_cost"),
            "net_profit_amount": self._computed.get("profit"),
            "net_profit_rate": self._computed.get("profit_rate"),
            "suggested_price_rmb": self._computed.get("suggested_price"),
            "converted_usd": self._computed.get("converted_usd"),
            "profit_before_adjustment": self._computed.get("profit_before_adjustment"),
            "profit_adjustment": self._computed.get("profit_adjustment"),
        }

    def save_product(self):
        inv = self._get_invalid_list()
        if inv:
            messagebox.showwarning("输入错误", "以下字段存在错误：\n\n" + "\n".join(f"  - {f}" for f in inv))
            return
        data = self._gather_data()
        rules = self._build_rule_snapshot()
        calc_results = self._build_calculation_snapshot()
        was_new = self._product_id is None
        try:
            self._product_id = self._db.save_product_state(
                data, rules, calc_results, pid=self._product_id
            )
        except Exception as exc:
            messagebox.showerror("保存失败", f"商品未保存，数据库已回滚：{exc}")
            return
        self._saved_rule_context = dict(rules)
        saved_adjustment = rules.get("profit_adjustment") or self._computed.get("profit_adjustment") or {}
        saved_rule = saved_adjustment.get("rule") if isinstance(saved_adjustment, dict) else None
        self._saved_profit_rule = dict(saved_rule) if saved_rule else None
        self._profit_rule_source = "frozen" if saved_rule else "none"
        self._profit_rule_explicitly_changed = False
        self._profit_rule_unavailable_notice = False
        if hasattr(self, "_profit_rule_var"):
            self._profit_rule_var.set(f"历史冻结规则：{saved_rule.get('display_name')}" if saved_rule else "无")
        if hasattr(self, "_profit_adjustment_var"):
            if not saved_rule:
                self._profit_adjustment_var.set("无规则")
            else:
                amt = saved_adjustment.get("amount_original") or 0
                cur = saved_adjustment.get("currency") or saved_rule.get("currency") or ""
                adj_rmb = saved_adjustment.get("adjustment_rmb") or 0
                self._profit_adjustment_var.set(
                    f"历史冻结规则：{saved_rule.get('display_name')}\n"
                    f"判断结果：{saved_adjustment.get('reason', '已保存')}\n"
                    f"调整：{amt:.2f} {cur}（{adj_rmb:+.2f} RMB）"
                )
        self._has_snapshot = True
        # 保存不清空页面（按 UI-602）
        if was_new:
            messagebox.showinfo("提示", f"商品已保存，ID: {self._product_id}")
        else:
            messagebox.showinfo("提示", f"商品 {self._product_id} 已更新。")

    def restore_product(self):
        if not self._product_id:
            messagebox.showinfo("提示", "尚未保存，无法还原。"); return
        snap = self._db.get_snapshot(self._product_id)
        if not snap:
            messagebox.showinfo("提示", "没有可还原的快照。"); return
        snapshot_rules = self._build_snapshot_rule_context(snap)
        if snapshot_rules:
            self._set_forwarder_key(snapshot_rules.get("forwarder", ""))
        self._load_data(snap)
        self._saved_rule_context = snapshot_rules
        adjustment = (snapshot_rules or {}).get("profit_adjustment") or {}
        rule = adjustment.get("rule") if isinstance(adjustment, dict) else None
        self._saved_profit_rule = dict(rule) if rule else None
        self._profit_rule_source = "frozen" if rule else "none"
        self._profit_rule_explicitly_changed = False; self._profit_rule_unavailable_notice = False
        if hasattr(self, "_profit_rule_var"):
            self._profit_rule_var.set(f"历史冻结规则：{rule.get('display_name')}" if rule else "无")
        self._populate_results_from_saved(snap, snap.get("_calculation_results"), snapshot_rules)
        messagebox.showinfo("提示", "已还原到首次保存的状态。")

    @staticmethod
    def _build_snapshot_rule_context(snapshot):
        if not snapshot: return None
        full = snapshot.get("_snapshot_rule_full")
        if isinstance(full, dict): return dict(full)
        return {
            "forwarder": snapshot.get("freight_forwarder"),
            "head_haul_rate": snapshot.get("_snapshot_head_haul_rate"),
            "fixed_service_fee": snapshot.get("_snapshot_fixed_service_fee"),
            "tail_haul_cost": snapshot.get("_snapshot_tail_haul_cost"),
            "exchange_rate": snapshot.get("_snapshot_exchange_rate"),
            "volume_divisor": snapshot.get("_snapshot_volume_divisor", VOLUME_DIVISOR),
            "rule_version": snapshot.get("_snapshot_rule_version"),
        }

    @staticmethod
    def _build_product_rule_context(product):
        rules = product.get("_current_rule_snapshot") if product else None
        return dict(rules) if isinstance(rules, dict) else None

    def _build_current_rule_context(self):
        fwd = self._get_forwarder_key()
        route = self._cfg.get_route_rates(fwd) if fwd else {}
        return {
            "route_id": fwd, "forwarder": fwd, "route_key": fwd,
            "route_display_name": route.get("display_name") if route else None,
            "head_haul_rate": route.get("head_haul_rate") if route else None,
            "fixed_service_fee": route.get("fixed_service_fee") if route else None,
            "tail_haul_cost": _safe_float(self._entry_vars.get("tail", tk.StringVar()).get()) if "tail" in self._entry_vars else self._cfg.default_tail_haul,
            "exchange_rate": self._cfg.exchange_rate,
            "volume_divisor": route.get("volume_divisor") if route else None,
            "rule_version": self._cfg.rule_version,
        }

    def _get_active_rule_context(self):
        if self._saved_rule_context is not None: return self._saved_rule_context
        return self._build_current_rule_context()

    def _load_data(self, data):
        self._programmatic = True
        try:
            for n, v in self._entry_vars.items():
                v.set("")
            self._var_name.set(data.get("name", ""))
            for key, attr in [("cost","cost"),("domestic_shipping","domestic"),
                              ("net_weight","net_w"),("net_length","net_l"),("net_width","net_wi"),("net_height","net_h"),
                              ("packaged_weight","pkg_w"),("packaged_length","pkg_l"),("packaged_width","pkg_wi"),("packaged_height","pkg_h"),
                              ("tail_haul_cost","tail"),("shein_price_usd","shein"),
                              ("price_rmb","price_rmb"),("price_usd","price_usd"),
                              ("target_profit_rate","target_rate"),("promo_rate","promo_rate")]:
                val = data.get(key)
                if val is not None and attr in self._entry_vars:
                    self._entry_vars[attr].set(_fmt(val) if isinstance(val, (int, float)) else str(val))
            if after_key := data.get("notes"):
                pass  # 暂不使用 notes
        finally: self._programmatic = False

    @staticmethod
    def _saved_result(calc, canonical_key, legacy_key=None):
        if not isinstance(calc, dict): return False, None
        if canonical_key in calc: return True, calc.get(canonical_key)
        if legacy_key and legacy_key in calc: return True, calc.get(legacy_key)
        return False, None

    def _populate_results_from_saved(self, data, calc=None, rule_context=None):
        rule_context = rule_context or {}
        if not hasattr(self, "_computed") or self._computed is None:
            self._computed = {}
        pkg_l = data.get("packaged_length"); pkg_wi = data.get("packaged_width")
        pkg_h = data.get("packaged_height"); pkg_w = data.get("packaged_weight")
        found, vol_w = self._saved_result(calc, "volumetric_weight")
        if not found or vol_w is None:
            vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h, rule_context.get("volume_divisor", VOLUME_DIVISOR))
        found, chg_w = self._saved_result(calc, "chargeable_weight")
        if not found or chg_w is None:
            chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("vol_weight", vol_w, " kg"); self._set_result("charge_weight", chg_w, " kg")
        found, head = self._saved_result(calc, "head_haul_cost", "head_haul")
        if not found: head = data.get("head_haul_cost")
        fwd = rule_context.get("forwarder") or data.get("freight_forwarder") or ""
        fwd_l = FORWARDER_LABELS.get(fwd, fwd) if fwd else ""
        if head is not None: self._set_result("head_haul", head, f" 元({fwd_l})" if fwd_l else " 元")
        else: self._set_result("head_haul", None, partial=True)
        fixed = data.get("fixed_service_fee"); tail = data.get("tail_haul_cost")
        missing = (head is None or fixed is None or tail is None)
        found, logistics = self._saved_result(calc, "total_logistics_cost", "total_logistics")
        if not found: logistics = total_logistics_cost(head, fixed, tail) if not missing else None
        cost = data.get("cost"); domestic = data.get("domestic_shipping")
        found, tc = self._saved_result(calc, "total_cost")
        if not found: tc = total_cost(cost, domestic, logistics) if logistics is not None else None
        self._set_result("total_logistics", logistics, " 元", partial=missing)
        self._set_result("total_cost", tc, " 元", partial=(not missing and tc is None))
        self._computed["forwarder"] = fwd
        self._computed["head_haul"] = head; self._computed["total_logistics"] = logistics
        self._computed["total_cost"] = tc; self._computed["volumetric_weight"] = vol_w
        self._computed["chargeable_weight"] = chg_w; self._computed["actual_weight_g"] = pkg_w
        self._computed["actual_weight_kg"] = pkg_w / 1000.0 if pkg_w else None
        # 利润：优先使用保存的计算结果，不重新计算
        found, np = self._saved_result(calc, "net_profit_amount", "profit")
        found_r, npr = self._saved_result(calc, "net_profit_rate", "profit_rate")
        if found:
            self._set_result("profit", np, " 元"); self._computed["profit"] = np
        if found_r:
            self._set_result("profit_rate", npr, " %"); self._computed["profit_rate"] = npr
        # 非金额字段
        found, converted = self._saved_result(calc, "converted_usd")
        if found: self._set_result("converted_usd", converted, " $")
        found, sp = self._saved_result(calc, "suggested_price_rmb", "suggested_price")
        if found: self._set_result("suggested_price", sp, " 元"); self._computed["suggested_price"] = sp
        # 恢复 profit_adjustment 到 _computed（保持冻结规则快照一致性）
        if isinstance(rule_context, dict) and rule_context.get("profit_adjustment"):
            self._computed["profit_adjustment"] = rule_context["profit_adjustment"]
        elif isinstance(calc, dict) and calc.get("profit_adjustment"):
            self._computed["profit_adjustment"] = calc["profit_adjustment"]
        if isinstance(calc, dict) and calc.get("profit_before_adjustment") is not None:
            self._computed["profit_before_adjustment"] = calc["profit_before_adjustment"]

    def load_product(self, product_id: str):
        product = self._db.get_product(product_id)
        if not product: messagebox.showerror("错误", f"未找到: {product_id}"); return
        if not hasattr(self, "_computed") or self._computed is None:
            self._computed = {}
        self._product_id = product_id
        self._has_snapshot = self._db.get_snapshot(product_id) is not None
        self._calc_direction = None; self._last_modified = None
        self._load_data(product)
        snap = self._db.get_snapshot(product_id)
        self._saved_rule_context = self._build_product_rule_context(product)
        if self._saved_rule_context is None and snap:
            self._saved_rule_context = self._build_snapshot_rule_context(snap)
        fwd = (self._saved_rule_context.get("forwarder") if self._saved_rule_context else product.get("freight_forwarder"))
        self._set_forwarder_key(fwd if fwd else "")
        adjustment = (self._saved_rule_context or {}).get("profit_adjustment") or {}
        adjustment_rule = adjustment.get("rule") if isinstance(adjustment, dict) else None
        self._saved_profit_rule = dict(adjustment_rule) if adjustment_rule else None
        self._profit_rule_source = "frozen" if adjustment_rule else "none"
        self._profit_rule_explicitly_changed = False; self._profit_rule_unavailable_notice = False
        if adjustment_rule and hasattr(self, "_profit_rule_var"):
            self._profit_rule_var.set(f"历史冻结规则：{adjustment_rule.get('display_name', '未命名规则')}")
        elif hasattr(self, "_profit_rule_var"):
            self._profit_rule_var.set("无")
        self._show_rate_banner = True
        self._populate_results_from_saved(product, product.get("_current_calculation_results"), self._saved_rule_context)
        if self._saved_rule_context: self._check_rate_changes()

    def _check_rate_changes(self):
        if not self._saved_rule_context: return
        current = self._build_current_rule_context()
        keys = {"head_haul_rate": "头程费率", "fixed_service_fee": "固定服务费", "tail_haul_cost": "尾程费用"}
        diffs = {}
        for k, label in keys.items():
            if k in self._saved_rule_context and k in current:
                sv = self._saved_rule_context.get(k); cv = current.get(k)
                if sv is not None and cv is not None and sv != cv: diffs[label] = (sv, cv)
        if diffs and self._show_rate_banner: self._show_rate_notice(diffs)
        else: self._show_rate_notice(None)
