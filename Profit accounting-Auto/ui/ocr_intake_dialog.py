"""OCR 录入弹窗 — 完整 GUI（上传/拖拽/粘贴/预览/编辑/回填）。

布局：顶部工具栏 | 左列表 | 右预览+类型 | 下候选编辑 | 底部确认/取消。
使用 IntakeService 管理文件，OcrIntakeController 管理逻辑状态。
"""
import io
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import PIL.Image
import PIL.ImageTk
import PIL.ImageGrab

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

from image_intake.image_types import ImageType, IMAGE_TYPE_LABELS
from image_intake.result_models import MeasurementScope
from image_intake.intake_controller import OcrIntakeController
from image_intake.intake_service import IntakeService, resolve_default_session_root

ALLOWED_EXT_TUPLE = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
SCOPE_LABELS = {
    MeasurementScope.BARE: "裸件",
    MeasurementScope.PACKAGED: "包装",
    MeasurementScope.UNKNOWN: "无法确认",
    MeasurementScope.NOT_APPLICABLE: "不适用",
}
PRICE_FIELDS = frozenset({"shein_price_usd", "product_cost_rmb", "domestic_shipping_rmb"})
DIMENSION_FIELDS = frozenset({"weight_g", "length_cm", "width_cm", "height_cm"})
FIELD_LABELS = {
    "shein_price_usd": "SHEIN核价($)", "product_cost_rmb": "商品成本(元)",
    "domestic_shipping_rmb": "国内运费(元)", "weight_g": "重量(g)",
    "length_cm": "长度(cm)", "width_cm": "宽度(cm)", "height_cm": "高度(cm)",
}


def _is_image_ext(name):
    return name.lower().endswith(ALLOWED_EXT_TUPLE)


class OcrIntakeDialog(tk.Toplevel):
    """OCR 录入对话框（完整 GUI）。"""

    def __init__(self, parent, controller=None, session_root=None, engine=None):
        super().__init__(parent)
        # 启用拖拽支持
        if _DND_AVAILABLE:
            try:
                TkinterDnD.require(self)
            except Exception:
                pass
        self.title("OCR 录入")
        self.geometry("1060x720")
        self.minsize(860, 580)
        self.transient(parent)
        self.grab_set()

        # ─── 服务与状态 ─────────────────────────────────────
        self._intake = IntakeService(
            session_root=session_root if session_root is not None else resolve_default_session_root(),
            engine=engine,
        )
        self._session = self._intake.create_session()
        self._controller = controller if controller is not None else OcrIntakeController(engine=engine)
        self.result = None
        self._preview_photo = None  # 保持引用
        self._current_image_id = None

        # ─── 构建 UI ────────────────────────────────────────
        self._build_toolbar()
        self._build_main()
        self._build_candidate_area()
        self._build_bottom()
        self._refresh_images()
        self._refresh_preview()

        # ─── 快捷键 ─────────────────────────────────────────
        self.bind("<Control-v>", lambda e: self._paste_from_clipboard())
        self.bind("<Control-V>", lambda e: self._paste_from_clipboard())

        # ─── 列表选中事件 ───────────────────────────────────
        self._img_list.bind("<<ListboxSelect>>", self._on_list_select)

    @property
    def controller(self):
        return self._controller

    # ═══════ 工具栏 ═════════════════════════════════════════

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(bar, text="上传图片", command=self._upload_images).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="粘贴图片", command=self._paste_from_clipboard).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="删除", command=self._delete_selected).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="替换", command=self._replace_selected).pack(side=tk.LEFT, padx=3)
        ttk.Label(bar, text="拖拽图片到列表或预览区", foreground="gray").pack(side=tk.RIGHT, padx=8)

    # ═══════ 主体：左列表 + 右预览 ──────────────────────────

    def _build_main(self):
        main = ttk.Frame(self)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=2)

        # 左：图片列表
        left = ttk.LabelFrame(main, text="图片列表", padding=4)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self._img_list = tk.Listbox(left, height=14, width=36, exportselection=False)
        self._img_list.pack(fill=tk.BOTH, expand=True)
        # 拖拽目标（若 DnD 不可用则静默跳过）
        if _DND_AVAILABLE:
            try:
                self._img_list.drop_target_register(DND_FILES)
                self._img_list.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        # 类型选择
        type_row = ttk.Frame(left)
        type_row.pack(fill=tk.X, pady=3)
        ttk.Label(type_row, text="类型：").pack(side=tk.LEFT)
        self._type_var = tk.StringVar()
        self._type_cb = ttk.Combobox(type_row, textvariable=self._type_var, state="readonly", width=20)
        self._type_cb["values"] = [IMAGE_TYPE_LABELS[t] for t in ImageType]
        self._type_cb.bind("<<ComboboxSelected>>", self._on_type_change)
        self._type_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 右：预览
        right = ttk.LabelFrame(main, text="预览", padding=4)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        if _DND_AVAILABLE:
            try:
                right.drop_target_register(DND_FILES)
                right.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        self._preview_label = ttk.Label(right, text="选择图片以预览", anchor=tk.CENTER,
                                         background="#e8e8e8", relief=tk.SUNKEN)
        self._preview_label.pack(fill=tk.BOTH, expand=True)
        self._info_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self._info_var, foreground="gray").pack(pady=2)

    # ═══════ 候选与编辑 ════════════════════════════════════
    # ═══════ 底部候选编辑区 ══════════════════════════════════

    def _build_candidate_area(self):
        """底部：候选列表 + 编辑控件。"""
        bottom = ttk.LabelFrame(self, text="候选编辑", padding=4)
        bottom.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(2, 0))

        # 候选列表（单行选中）
        cols = ("field", "value", "unit", "source", "raw", "conf", "sel")
        self._cand_tree = ttk.Treeview(bottom, columns=cols, show="headings", height=6)
        h = {"field": "字段", "value": "值", "unit": "单位", "source": "来源",
             "raw": "原文", "conf": "置信度", "sel": "可选"}
        for c in cols:
            self._cand_tree.heading(c, text=h[c])
            self._cand_tree.column(c, width=100, anchor=tk.CENTER)
        self._cand_tree.pack(fill=tk.BOTH, expand=True, pady=2)
        self._cand_tree.bind("<<TreeviewSelect>>", self._on_candidate_select)

        # 编辑行
        edit_row = ttk.Frame(bottom)
        edit_row.pack(fill=tk.X, pady=2)

        ttk.Label(edit_row, text="确认值：").pack(side=tk.LEFT)
        self._edit_value_var = tk.StringVar()
        self._edit_value_entry = ttk.Entry(edit_row, textvariable=self._edit_value_var, width=10)
        self._edit_value_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(edit_row, text="单位：").pack(side=tk.LEFT, padx=(8, 0))
        self._edit_unit_var = tk.StringVar()
        self._edit_unit_cb = ttk.Combobox(edit_row, textvariable=self._edit_unit_var, width=8)
        self._edit_unit_cb.pack(side=tk.LEFT, padx=2)

        ttk.Label(edit_row, text="scope：").pack(side=tk.LEFT, padx=(8, 0))
        self._edit_scope_var = tk.StringVar()
        self._edit_scope_cb = ttk.Combobox(edit_row, textvariable=self._edit_scope_var, state="readonly", width=10)
        self._edit_scope_cb["values"] = [SCOPE_LABELS[s] for s in MeasurementScope]
        self._edit_scope_cb.pack(side=tk.LEFT, padx=2)

        ttk.Button(edit_row, text="应用修改", command=self._apply_edit).pack(side=tk.LEFT, padx=(10, 0))

        # 选中候选信息（只读）
        info_row = ttk.Frame(bottom)
        info_row.pack(fill=tk.X, pady=1)
        self._sel_info_var = tk.StringVar(value="未选中候选")
        ttk.Label(info_row, textvariable=self._sel_info_var, foreground="gray").pack(side=tk.LEFT)

    # ═══════ 底部确认 ─══════════════════════════════════════

    def _build_bottom(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self._status_var, foreground="gray").pack(side=tk.LEFT)
        ttk.Button(bar, text="处理图片", command=self._process_images).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="确认并填入商品", command=self._on_confirm).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bar, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=3)

    # ═══════ 上传图片 ══════════════════════════════════════

    def _upload_images(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="选择图片",
            filetypes=[("图片文件", " ".join(f"*{e}" for e in ALLOWED_EXT_TUPLE)), ("全部", "*.*")],
        )
        if not paths:
            return
        self._add_files_to_session(paths)
        self._sync_and_refresh()

    # ═══════ 拖拽图片 ══════════════════════════════════════

    def _on_drop(self, event):
        if not _DND_AVAILABLE:
            return
        raw_paths = self.tk.splitlist(event.data) if hasattr(self, "tk") else event.data
        valid = []
        for p in raw_paths:
            # tkinterdnd2 可能用花括号包裹含空格的路径
            p = p.strip("{}")
            if _is_image_ext(p) and os.path.isfile(p):
                valid.append(p)
            elif os.path.isdir(p):
                messagebox.showinfo("提示", f"不支持文件夹：{os.path.basename(p)}", parent=self)
            elif p:
                messagebox.showinfo("提示", f"不支持的文件类型：{os.path.basename(p)}", parent=self)
        if valid:
            self._add_files_to_session(valid)
            self._sync_and_refresh()

    # ═══════ 粘贴图片 ══════════════════════════════════════

    def _paste_from_clipboard(self):
        try:
            clip = PIL.ImageGrab.grabclipboard()
        except Exception as exc:
            messagebox.showwarning("剪贴板", f"无法读取剪贴板：{exc}", parent=self)
            return
        if clip is None:
            messagebox.showinfo("提示", "剪贴板中没有可用图片", parent=self)
            return
        if isinstance(clip, PIL.Image.Image):
            buf = io.BytesIO()
            clip.convert("RGB").save(buf, format="PNG")
            data = buf.getvalue()
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"clipboard_{now}.png"
            rec = self._intake.add_image_bytes(self._session, data, fname, ImageType.SUPPLEMENTARY)
            self._controller.register_image(rec["image_id"], rec["stored_path"], ImageType.SUPPLEMENTARY, fname)
            self._sync_and_refresh()
        elif isinstance(clip, list):
            valid = [p for p in clip if _is_image_ext(str(p)) and os.path.isfile(str(p))]
            if valid:
                self._add_files_to_session(valid)
                self._sync_and_refresh()
            else:
                messagebox.showinfo("提示", "剪贴板中没有可用图片文件", parent=self)
        else:
            messagebox.showinfo("提示", "剪贴板中没有可用图片", parent=self)

    # ═══════ 删除/替换/类型 ─────────────────────────────────

    def _delete_selected(self):
        sel = self._img_list.curselection()
        if not sel:
            return
        idx = sel[0]
        img = self._controller.images[idx]
        if not messagebox.askyesno("确认", f"确定删除图片 {img['filename']}？\n（不会删除原始文件）", parent=self):
            return
        self._controller.remove_image(img["image_id"])
        self._sync_and_refresh()

    def _replace_selected(self):
        sel = self._img_list.curselection()
        if not sel:
            return
        old_img = self._controller.images[sel[0]]
        new_path = filedialog.askopenfilename(
            parent=self, title="选择替换图片",
            filetypes=[("图片文件", " ".join(f"*{e}" for e in ALLOWED_EXT_TUPLE))],
        )
        if not new_path:
            return
        self._add_files_to_session([new_path], force_type=old_img["image_type"])
        self._controller.remove_image(old_img["image_id"])
        self._sync_and_refresh()

    def _on_type_change(self, event=None):
        sel = self._img_list.curselection()
        if not sel:
            return
        label = self._type_var.get()
        for t in ImageType:
            if IMAGE_TYPE_LABELS[t] == label:
                img = self._controller.images[sel[0]]
                self._controller.set_image_type(img["image_id"], t)
                self._refresh_images()
                self._status_var.set(f"类型已改为 {label}")
                return

    # ═══════ 候选编辑 ─══════════════════════════════════════

    def _on_candidate_select(self, event=None):
        sel = self._cand_tree.selection()
        if not sel:
            self._sel_info_var.set("未选中候选")
            return
        cid = sel[0]
        c = self._controller.candidate_by_id(cid)
        if c is None:
            self._sel_info_var.set("候选不存在")
            return
        field_label = FIELD_LABELS.get(c.field_name, c.field_name)
        self._sel_info_var.set(f"字段：{field_label}  来源：{c.source_image[:8]}  OCR原文：{c.raw_text}  OCR值：{c.parsed_value}")
        # 填充编辑控件
        existing = self._controller.selections.get(c.field_name)
        if existing and existing.source_candidate_id == cid:
            self._edit_value_var.set(str(existing.confirmed_value) if existing.confirmed_value is not None else "")
            self._edit_unit_var.set(existing.confirmed_unit or "")
            self._edit_scope_var.set(SCOPE_LABELS.get(existing.measurement_scope, ""))
        else:
            self._edit_value_var.set(str(c.normalized_value) if c.normalized_value is not None else "")
            self._edit_unit_var.set(c.unit_normalized or "")
            if c.field_name in PRICE_FIELDS:
                self._edit_scope_var.set(SCOPE_LABELS[MeasurementScope.NOT_APPLICABLE])
            else:
                self._edit_scope_var.set(SCOPE_LABELS[MeasurementScope.UNKNOWN])
        # 单位下拉
        if c.field_name == "shein_price_usd":
            self._edit_unit_cb["values"] = ["usd"]
        elif c.field_name in ("product_cost_rmb", "domestic_shipping_rmb"):
            self._edit_unit_cb["values"] = ["rmb"]
        elif c.field_name == "weight_g":
            self._edit_unit_cb["values"] = ["g", "kg"]
        elif c.field_name in ("length_cm", "width_cm", "height_cm"):
            self._edit_unit_cb["values"] = ["cm", "mm"]
        else:
            self._edit_unit_cb["values"] = [c.unit_normalized or ""]
        # scope 下拉
        if c.field_name in PRICE_FIELDS:
            self._edit_scope_cb["values"] = [SCOPE_LABELS[MeasurementScope.NOT_APPLICABLE]]
        else:
            self._edit_scope_cb["values"] = [SCOPE_LABELS[s] for s in
                                              (MeasurementScope.BARE, MeasurementScope.PACKAGED, MeasurementScope.UNKNOWN)]

    def _apply_edit(self):
        sel = self._cand_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择候选", parent=self)
            return
        cid = sel[0]
        c = self._controller.candidate_by_id(cid)
        if c is None:
            return
        value_str = self._edit_value_var.get().strip()
        unit = self._edit_unit_var.get().strip()

        # 解析数值
        try:
            if not value_str:
                raise ValueError("值不能为空")
            v = float(value_str)
        except (ValueError, TypeError):
            messagebox.showerror("输入错误", f"非法数值：{value_str}", parent=self)
            return

        # 解析 scope
        scope_label = self._edit_scope_var.get()
        scope = None
        for s in MeasurementScope:
            if SCOPE_LABELS[s] == scope_label:
                scope = s
                break

        try:
            if c.selectable:
                # 可选候选：直接用 edit_confirmed_value
                if c.field_name not in self._controller.selections:
                    self._controller.select_candidate(c.field_name, cid)
                self._controller.edit_confirmed_value(c.field_name, v, unit)
                if scope and scope != self._controller.selections[c.field_name].measurement_scope:
                    self._controller.set_measurement_scope(c.field_name, scope)
            else:
                # 不可选候选：用 confirm_candidate_manual
                self._controller.confirm_candidate_manual(c.field_name, cid, v, unit, scope)
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc), parent=self)
            return
        self._status_var.set(f"已修改 {c.field_name}")
        self._refresh_candidates()

    # ═══════ 处理与确认 ─═══════════════════════════════════

    def _process_images(self):
        self._controller.process_all()
        self._refresh_candidates()
        err = self._controller.last_error
        if err:
            self._status_var.set(f"警告：{err}")
        else:
            self._status_var.set(f"候选 {len(self._controller.candidates)} 条")

    def _on_confirm(self):
        try:
            self.result = self._controller.confirm()
        except RuntimeError as exc:
            messagebox.showerror("无法确认", str(exc), parent=self)
            return
        self._intake.save_session(self._session)
        self.destroy()

    # ═══════ 辅助方法 ═══════════════════════════════════════

    def _add_files_to_session(self, paths, force_type=None):
        """批量添加文件到 IntakeService session。跳过非图片，单张失败不中断。"""
        added = 0
        for p in paths:
            p = str(p)
            if not _is_image_ext(p):
                messagebox.showinfo("提示", f"不支持的文件：{os.path.basename(p)}", parent=self)
                continue
            if not os.path.isfile(p):
                messagebox.showinfo("提示", f"文件不存在：{p}", parent=self)
                continue
            try:
                img_type = force_type if force_type else ImageType.SUPPLEMENTARY
                rec = self._intake.add_image(self._session, p, img_type)
                self._controller.register_image(rec["image_id"], rec["stored_path"], img_type, rec["original_filename"])
                added += 1
            except Exception as exc:
                messagebox.showinfo("提示", f"添加失败 {os.path.basename(p)}：{exc}", parent=self)
        if added > 0:
            self._intake.save_session(self._session)

    def _sync_and_refresh(self):
        self._refresh_images()
        self._refresh_preview()
        self._controller.process_all()
        self._refresh_candidates()

    def _refresh_images(self):
        self._img_list.delete(0, tk.END)
        for img in self._controller.images:
            label = IMAGE_TYPE_LABELS.get(img["image_type"], img["image_type"].value)
            self._img_list.insert(tk.END, f"{img['filename']} [{label}]")
        # 自动选中第一张
        if self._controller.images and not self._img_list.curselection():
            self._img_list.selection_set(0)
            self._img_list.activate(0)
            self._on_list_select()

    def _on_list_select(self, event=None):
        sel = self._img_list.curselection()
        if not sel:
            self._current_image_id = None
            self._refresh_preview()
            return
        idx = sel[0]
        imgs = self._controller.images
        if idx < len(imgs):
            img = imgs[idx]
            self._current_image_id = img["image_id"]
            # 更新类型下拉
            label = IMAGE_TYPE_LABELS.get(img["image_type"], img["image_type"].value)
            self._type_var.set(label)
            self._refresh_preview()

    def _refresh_preview(self):
        self._preview_photo = None  # 释放旧引用
        img_id = self._current_image_id
        if img_id is None:
            self._preview_label.config(image="", text="选择图片以预览", background="#e8e8e8")
            self._info_var.set("")
            return
        img = next((i for i in self._controller.images if i["image_id"] == img_id), None)
        if img is None:
            self._preview_label.config(image="", text="图片不存在", background="#e8e8e8")
            self._info_var.set("")
            return
        path = img["path"]
        self._info_var.set(f"{img['filename']}  [{IMAGE_TYPE_LABELS.get(img['image_type'], '')}]")
        try:
            pil_img = PIL.Image.open(path)
            w, h = pil_img.size
            # 缩放适配预览区（约 400×300 max）
            max_w, max_h = 400, 300
            pil_img.thumbnail((max_w, max_h), PIL.Image.LANCZOS)
            self._preview_photo = PIL.ImageTk.PhotoImage(pil_img)
            self._preview_label.config(image=self._preview_photo, text="", background="white",
                                        compound=tk.NONE)
            self._info_var.set(f"{img['filename']}  [{IMAGE_TYPE_LABELS.get(img['image_type'], '')}]  {w}×{h} px")
        except Exception as exc:
            self._preview_label.config(image="", text=f"无法预览：{exc}", background="#e8e8e8")
            self._info_var.set("文件损坏")

    def _refresh_candidates(self):
        self._cand_tree.delete(*self._cand_tree.get_children())
        for c in self._controller.candidates:
            has_sel = c.candidate_id in {s.source_candidate_id for s in self._controller.selections.values()}
            self._cand_tree.insert("", tk.END, iid=c.candidate_id, values=(
                FIELD_LABELS.get(c.field_name, c.field_name),
                f"{c.normalized_value}" if c.normalized_value is not None else "-",
                c.unit_normalized or "-",
                c.source_image[:8],
                c.raw_text,
                f"{c.confidence:.2f}",
                "是" if c.selectable else ("是*" if has_sel else "否"),
            ))
        # 更新状态
        sel_count = len(self._controller.selections)
        total = len(self._controller.candidates)
        self._status_var.set(f"图片 {len(self._controller.images)} 张  候选 {total} 条  已选 {sel_count} 项")
