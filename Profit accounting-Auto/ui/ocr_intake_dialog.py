"""OCR 录入弹窗（Tkinter Toplevel）。

UI 层只做展示，逻辑在 OcrIntakeController。
确认后结果存在 self.result（dict[field_name, FieldSelection]），不写入正式商品字段。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk, messagebox

from image_intake.intake_controller import OcrIntakeController
from image_intake.image_types import ImageType, IMAGE_TYPE_LABELS
from image_intake.result_models import MeasurementScope


SCOPE_LABELS = {
    MeasurementScope.BARE: "裸件",
    MeasurementScope.PACKAGED: "包装",
    MeasurementScope.UNKNOWN: "无法确认",
    MeasurementScope.NOT_APPLICABLE: "不适用",
}


class OcrIntakeDialog(tk.Toplevel):
    """OCR 录入对话框。

    用法：
        dlg = OcrIntakeDialog(root, controller=ctrl)
        root.wait_window(dlg)
        if dlg.result:
            # result 是 dict[field_name, FieldSelection]
    """

    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.title("OCR 录入")
        self.geometry("960x620")
        self.transient(parent)
        self.grab_set()
        self._controller = controller if controller is not None else OcrIntakeController()
        self.result = None
        self._build_ui()
        self._refresh_images()

    @property
    def controller(self):
        return self._controller

    def _build_ui(self):
        # 左：图片列表
        left = ttk.LabelFrame(self, text="图片列表", padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=6, pady=6)
        self._img_list = tk.Listbox(left, height=18, width=32)
        self._img_list.pack(fill=tk.BOTH, expand=True)
        type_frame = ttk.Frame(left)
        type_frame.pack(fill=tk.X, pady=4)
        ttk.Label(type_frame, text="类型：").pack(side=tk.LEFT)
        self._type_var = tk.StringVar()
        self._type_cb = ttk.Combobox(type_frame, textvariable=self._type_var, state="readonly", width=18)
        self._type_cb["values"] = [IMAGE_TYPE_LABELS[t] for t in ImageType]
        self._type_cb.pack(side=tk.LEFT)

        # 右：候选列表
        right = ttk.LabelFrame(self, text="候选列表", padding=8)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        cols = ("field", "value", "unit", "source", "raw", "conf", "selectable")
        self._cand_tree = ttk.Treeview(right, columns=cols, show="headings", height=18)
        headings = {
            "field": "字段", "value": "值", "unit": "单位", "source": "来源",
            "raw": "原文", "conf": "置信度", "selectable": "可选",
        }
        for c in cols:
            self._cand_tree.heading(c, text=headings[c])
            self._cand_tree.column(c, width=90)
        self._cand_tree.pack(fill=tk.BOTH, expand=True)

        # scope 下拉
        scope_frame = ttk.Frame(right)
        scope_frame.pack(fill=tk.X, pady=4)
        ttk.Label(scope_frame, text="scope：").pack(side=tk.LEFT)
        self._scope_var = tk.StringVar()
        self._scope_cb = ttk.Combobox(scope_frame, textvariable=self._scope_var, state="readonly", width=12)
        self._scope_cb["values"] = [SCOPE_LABELS[s] for s in MeasurementScope]
        self._scope_cb.pack(side=tk.LEFT)

        # 底部按钮
        bar = ttk.Frame(self)
        bar.pack(side=tk.BOTTOM, fill=tk.X, pady=4)
        ttk.Button(bar, text="处理图片", command=self._on_process).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="确认", command=self._on_confirm).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=4)
        self._status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self._status_var, foreground="gray").pack(side=tk.RIGHT, padx=8)

    def _refresh_images(self):
        self._img_list.delete(0, tk.END)
        for img in self._controller.images:
            label = IMAGE_TYPE_LABELS.get(img["image_type"], img["image_type"].value)
            self._img_list.insert(tk.END, f"{img['filename']} [{label}]")

    def _refresh_candidates(self):
        self._cand_tree.delete(*self._cand_tree.get_children())
        for c in self._controller.candidates:
            self._cand_tree.insert("", tk.END, iid=c.candidate_id, values=(
                c.field_name, c.normalized_value, c.unit_normalized,
                c.source_image[:8], c.raw_text, f"{c.confidence:.2f}",
                "是" if c.selectable else "否",
            ))
        err = self._controller.last_error
        self._status_var.set(err or f"候选 {len(self._controller.candidates)} 条")

    def _on_process(self):
        self._controller.process_all()
        self._refresh_candidates()

    def _on_confirm(self):
        try:
            self.result = self._controller.confirm()
        except RuntimeError as exc:
            messagebox.showerror("无法确认", str(exc), parent=self)
            return
        self.destroy()
