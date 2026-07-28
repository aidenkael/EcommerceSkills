"""
主窗口模块

包含菜单栏、设置对话框、两个标签页（新商品测算 / 历史记录）。
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import math
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .product_page import ProductPage
from .history_page import HistoryPage
from config.forwarder_manager import ForwarderManager
from config.profit_adjustment_manager import ProfitAdjustmentManager


class ProfitRulesDialog(tk.Toplevel):
    """利润调整规则编辑器 — Phase 1.6 review 修复版

    修复：
    - 中文映射下拉框替代英文代码输入
    - 增加 description 字段
    - 未保存修改保护（新增/切换/关闭）
    - 归档规则禁止通过保存恢复
    - 字段联动（无条件/固定金额/百分比）
    """

    # 中文 ↔ 内部值映射
    CONDITION_FIELDS = [("", "无条件"), ("final_price_usd", "最终售价（美元）"), ("final_price_rmb", "最终售价（人民币）"), ("product_cost_rmb", "商品成本（人民币）"), ("logistics_cost_rmb", "物流成本（人民币）")]
    OPERATORS = [("<", "小于"), ("<=", "小于等于"), (">", "大于"), (">=", "大于等于"), ("==", "等于")]
    DIRECTIONS = [("income", "增加收入"), ("cost", "增加成本")]
    TYPES = [("fixed", "固定金额"), ("percent", "百分比")]
    CURRENCIES = [("USD", "美元"), ("RMB", "人民币")]
    PERCENTAGE_BASES = [("", ""), ("final_price_rmb", "最终售价人民币"), ("product_cost_rmb", "商品成本人民币"), ("logistics_cost_rmb", "物流成本人民币")]

    def __init__(self, parent, config_manager, on_change=None):
        super().__init__(parent)
        self._cfg = config_manager
        self._manager = ProfitAdjustmentManager(config_manager._db)
        self._on_change = on_change
        self.title("利润调整规则"); self.geometry("900x500"); self.transient(parent); self.grab_set()
        self._selected_id = None
        self._dirty = False; self._suspend_dirty = False
        self._vars = {key: tk.StringVar() for key in ("display_name", "condition_field", "condition_operator", "condition_value", "adjustment_direction", "adjustment_type", "adjustment_value", "currency", "percentage_base", "description")}
        self._enabled = tk.BooleanVar(value=True)
        # 跟踪修改
        for var in self._vars.values(): var.trace_add("write", lambda *_: self._mark_dirty())
        self._enabled.trace_add("write", lambda *_: self._mark_dirty())
        self._build_ui()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._try_close)

    def _mark_dirty(self):
        if not self._suspend_dirty: self._dirty = True

    def _programmatic(self, action):
        self._suspend_dirty = True
        try: action()
        finally: self._suspend_dirty = False
        self._dirty = False

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10); outer.pack(fill=tk.BOTH, expand=True)
        self._list = tk.Listbox(outer, height=10, width=60); self._list.grid(row=0, column=0, columnspan=6, sticky="nsew")
        self._list.bind("<<ListboxSelect>>", self._select)
        # 表单行 1
        r = 1
        ttk.Label(outer, text="名称：").grid(row=r, column=0, sticky=tk.W, padx=3, pady=3)
        self._name_entry = ttk.Entry(outer, textvariable=self._vars["display_name"], width=25)
        self._name_entry.grid(row=r, column=1, columnspan=2, sticky=tk.EW, padx=3, pady=3)
        # 行 2：条件
        r += 1
        ttk.Label(outer, text="条件：").grid(row=r, column=0, sticky=tk.W, padx=3, pady=3)
        self._cond_cb = ttk.Combobox(outer, textvariable=self._vars["condition_field"], values=[v[1] for v in self.CONDITION_FIELDS], state="readonly", width=18)
        self._cond_cb.grid(row=r, column=1, sticky=tk.EW, padx=3, pady=3); self._cond_cb.bind("<<ComboboxSelected>>", self._on_condition_change)
        self._op_cb = ttk.Combobox(outer, textvariable=self._vars["condition_operator"], values=[v[1] for v in self.OPERATORS], state="readonly", width=10)
        self._op_cb.grid(row=r, column=2, sticky=tk.EW, padx=3, pady=3)
        self._cond_val_entry = ttk.Entry(outer, textvariable=self._vars["condition_value"], width=12)
        self._cond_val_entry.grid(row=r, column=3, sticky=tk.EW, padx=3, pady=3)
        # 行 3：调整
        r += 1
        ttk.Label(outer, text="调整方向：").grid(row=r, column=0, sticky=tk.W, padx=3, pady=3)
        self._direction_cb = ttk.Combobox(outer, textvariable=self._vars["adjustment_direction"], values=[v[1] for v in self.DIRECTIONS], state="readonly", width=15)
        self._direction_cb.grid(row=r, column=1, sticky=tk.EW, padx=3, pady=3)
        ttk.Label(outer, text="类型：").grid(row=r, column=2, sticky=tk.W, padx=3, pady=3)
        self._type_cb = ttk.Combobox(outer, textvariable=self._vars["adjustment_type"], values=[v[1] for v in self.TYPES], state="readonly", width=12)
        self._type_cb.grid(row=r, column=3, sticky=tk.EW, padx=3, pady=3); self._type_cb.bind("<<ComboboxSelected>>", self._on_type_change)
        # 行 4：金额/比例
        r += 1
        self._val_label = ttk.Label(outer, text="金额：")
        self._val_label.grid(row=r, column=0, sticky=tk.W, padx=3, pady=3)
        self._adjustment_entry = ttk.Entry(outer, textvariable=self._vars["adjustment_value"], width=15)
        self._adjustment_entry.grid(row=r, column=1, sticky=tk.EW, padx=3, pady=3)
        ttk.Label(outer, text="币种：").grid(row=r, column=2, sticky=tk.W, padx=3, pady=3)
        self._currency_cb = ttk.Combobox(outer, textvariable=self._vars["currency"], values=[v[1] for v in self.CURRENCIES], state="readonly", width=8)
        self._currency_cb.grid(row=r, column=3, sticky=tk.EW, padx=3, pady=3)
        # 行 5：百分比基数
        r += 1
        ttk.Label(outer, text="百分比基数：").grid(row=r, column=0, sticky=tk.W, padx=3, pady=3)
        self._base_cb = ttk.Combobox(outer, textvariable=self._vars["percentage_base"], values=[v[1] for v in self.PERCENTAGE_BASES if v[0]], state="readonly", width=18)
        self._base_cb.grid(row=r, column=1, columnspan=2, sticky=tk.EW, padx=3, pady=3)
        # 行 6：说明
        r += 1
        ttk.Label(outer, text="说明：").grid(row=r, column=0, sticky=tk.W, padx=3, pady=3)
        self._description_entry = ttk.Entry(outer, textvariable=self._vars["description"], width=50)
        self._description_entry.grid(row=r, column=1, columnspan=4, sticky=tk.EW, padx=3, pady=3)
        # 行 7
        r += 1
        self._enabled_check = ttk.Checkbutton(outer, text="启用", variable=self._enabled)
        self._enabled_check.grid(row=r, column=0, sticky=tk.W)
        self._status_var = tk.StringVar(); ttk.Label(outer, textvariable=self._status_var, foreground="gray").grid(row=r, column=1, columnspan=4, sticky=tk.W)
        # 按钮
        r += 1
        bar = ttk.Frame(outer); bar.grid(row=r, column=0, columnspan=6, pady=8)
        self._new_button = ttk.Button(bar, text="新增", command=self._new); self._new_button.pack(side=tk.LEFT, padx=3)
        self._save_button = ttk.Button(bar, text="保存", command=self._save); self._save_button.pack(side=tk.LEFT, padx=3)
        self._archive_button = ttk.Button(bar, text="归档/删除", command=self._archive); self._archive_button.pack(side=tk.LEFT, padx=3)
        self._restore_button = ttk.Button(bar, text="恢复", command=self._restore); self._restore_button.pack(side=tk.LEFT, padx=3)
        self._close_button = ttk.Button(bar, text="关闭", command=self._try_close); self._close_button.pack(side=tk.LEFT, padx=3)
        outer.columnconfigure(1, weight=1); outer.columnconfigure(3, weight=1); outer.columnconfigure(5, weight=1)

    def _get_internal(self, display_str, mapping):
        for key, label in mapping:
            if label == display_str: return key
        return display_str if display_str else None

    def _get_display(self, internal, mapping):
        for key, label in mapping:
            if key == internal: return label
        return internal or ""

    def _on_condition_change(self, _event=None):
        cond = self._vars["condition_field"].get()
        if cond == "无条件" or not cond:
            self._op_cb.config(state="disabled"); self._vars["condition_operator"].set("")
            self._cond_val_entry.config(state="disabled"); self._vars["condition_value"].set("")
        else:
            self._op_cb.config(state="readonly"); self._cond_val_entry.config(state="normal")
            if not self._vars["condition_operator"].get(): self._vars["condition_operator"].set("小于")

    def _on_type_change(self, _event=None):
        typ = self._vars["adjustment_type"].get()
        if typ == "固定金额":
            self._val_label.config(text="金额：")
            self._base_cb.config(state="disabled"); self._vars["percentage_base"].set("")
            self._currency_cb.config(state="readonly")
        else:
            self._val_label.config(text="比例 (%)：")
            self._base_cb.config(state="readonly")
            if not self._vars["percentage_base"].get(): self._vars["percentage_base"].set("最终售价人民币")
            self._currency_cb.config(state="disabled"); self._vars["currency"].set("")

    def _check_dirty(self, action_desc="操作"):
        """检查未保存修改，返回 True 继续 / False 取消"""
        if not self._dirty: return True
        result = messagebox.askyesnocancel(
            "未保存修改", f"当前规则有未保存的修改。\n是否保存后再{action_desc}？\n\n是 = 保存并继续\n否 = 放弃修改并继续\n取消 = 保持当前编辑",
            parent=self, default=messagebox.CANCEL)
        if result is None: return False  # 取消
        if result:  # 是 = 保存并继续
            return self._save_internal()
        # 否 = 放弃修改
        self._dirty = False; self._load_current()
        return True

    def _save_internal(self):
        """内部保存，返回 True 成功"""
        try:
            if self._selected_id is None:
                self._selected_id = self._manager.create(self._values())
            else:
                self._manager.update(self._selected_id, self._values())
            self._dirty = False; self._refresh(); self._restore_list_selection(); self._load_current(); self._update_status()
            return True
        except ValueError as exc:
            messagebox.showerror("规则错误", str(exc), parent=self)
            return False
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return False

    def _refresh(self):
        self._rows = self._manager.list(True)
        self._list.delete(0, tk.END)
        for item in self._rows:
            prefix = "[归档] " if item["is_archived"] else ("[停用] " if not item["is_enabled"] else "")
            cond = self._get_display(item.get("condition_field"), self.CONDITION_FIELDS) or "无条件"
            op = self._get_display(item.get("condition_operator"), self.OPERATORS) or ""
            cv = "" if item.get("condition_value") is None else item.get("condition_value")
            typ = "固定金额" if item.get("adjustment_type") == "fixed" else "百分比"
            cur = self._get_display(item.get("currency"), self.CURRENCIES) or ""
            val = 0 if item.get("adjustment_value") is None else item.get("adjustment_value")
            direction = "增加收入" if item.get("adjustment_direction") == "income" else "增加成本"
            base = self._get_display(item.get("percentage_base"), self.PERCENTAGE_BASES)
            amount = f"{base}的 {val}%" if item.get("adjustment_type") == "percent" else f"{val} {cur}"
            self._list.insert(tk.END, f"{prefix}{item['display_name']} | {cond} {op} {cv} | {direction}/{typ} {amount}")
        if self._on_change: self._on_change()

    def _new(self):
        if not self._check_dirty("新建"): return
        self._selected_id = None; self._dirty = False; self._suspend_dirty = True
        self._list.selection_clear(0, tk.END)
        defaults = {"display_name":"", "condition_field":"无条件", "condition_operator":"", "condition_value":"",
                    "adjustment_direction":"增加收入", "adjustment_type":"固定金额", "adjustment_value":"",
                    "currency":"美元", "percentage_base":"", "description":""}
        for key, value in defaults.items(): self._vars[key].set(value)
        self._enabled.set(True); self._on_condition_change(); self._on_type_change(); self._suspend_dirty = False; self._dirty = False
        self._set_editor_read_only(False)

    def _select(self, _event):
        sel = self._list.curselection()
        if not sel: return
        target_id = self._rows[sel[0]]["rule_id"]
        if not self._check_dirty("切换规则"):
            self._restore_list_selection()
            return
        self._selected_id = target_id
        self._restore_list_selection()
        self._load_current()

    def _load_current(self):
        """重新载入当前选中规则的数据库值。"""
        self._suspend_dirty = True
        item = next((r for r in self._rows if r["rule_id"] == self._selected_id), None) if self._selected_id else None
        if item:
            self._vars["display_name"].set(item.get("display_name", ""))
            self._vars["condition_field"].set(self._get_display(item.get("condition_field"), self.CONDITION_FIELDS) or "无条件")
            self._vars["condition_operator"].set(self._get_display(item.get("condition_operator"), self.OPERATORS) or "")
            self._vars["condition_value"].set("" if item.get("condition_value") is None else str(item.get("condition_value")))
            self._vars["adjustment_direction"].set(self._get_display(item.get("adjustment_direction"), self.DIRECTIONS) or "增加收入")
            self._vars["adjustment_type"].set(self._get_display(item.get("adjustment_type"), self.TYPES) or "固定金额")
            self._vars["adjustment_value"].set("" if item.get("adjustment_value") is None else str(item.get("adjustment_value")))
            self._vars["currency"].set(self._get_display(item.get("currency"), self.CURRENCIES) or "美元")
            self._vars["percentage_base"].set(self._get_display(item.get("percentage_base"), self.PERCENTAGE_BASES) or "")
            self._vars["description"].set(item.get("description", ""))
            self._enabled.set(item.get("is_enabled", True))
        self._on_condition_change(); self._on_type_change(); self._suspend_dirty = False; self._dirty = False
        self._update_status()

    def _restore_list_selection(self):
        """按稳定 rule_id 恢复列表选中项，避免取消切换后列表与表单不一致。"""
        if not hasattr(self, "_list"):
            return
        self._list.selection_clear(0, tk.END)
        for index, item in enumerate(getattr(self, "_rows", [])):
            if item.get("rule_id") == self._selected_id:
                self._list.selection_set(index)
                self._list.activate(index)
                self._list.see(index)
                break


    def _update_status(self):
        item = next((r for r in self._rows if r["rule_id"] == self._selected_id), None) if self._selected_id else None
        if item and item.get("is_archived"):
            self._status_var.set("已归档（只读）— 点恢复后可编辑")
        elif item and not item.get("is_enabled"):
            self._status_var.set("已停用")
        else:
            self._status_var.set("")
        self._set_editor_read_only(bool(item and item.get("is_archived")))

    def _set_editor_read_only(self, archived):
        """归档规则只允许恢复或关闭；恢复后由调用方重新载入可编辑状态。"""
        was_suspended = self._suspend_dirty
        self._suspend_dirty = True
        try:
            normal = "disabled" if archived else "normal"
            combo = "disabled" if archived else "readonly"
            for widget in (getattr(self, "_name_entry", None), getattr(self, "_cond_val_entry", None),
                           getattr(self, "_adjustment_entry", None), getattr(self, "_description_entry", None),
                           getattr(self, "_enabled_check", None)):
                if widget is not None:
                    widget.config(state=normal)
            for widget in (getattr(self, "_cond_cb", None), getattr(self, "_op_cb", None),
                           getattr(self, "_direction_cb", None), getattr(self, "_type_cb", None),
                           getattr(self, "_currency_cb", None), getattr(self, "_base_cb", None)):
                if widget is not None:
                    widget.config(state=combo)
            # 条件/类型联动会对这些控件设置特殊状态；归档时必须覆盖为禁用。
            if not archived:
                self._on_condition_change()
                self._on_type_change()
            for widget, state in ((getattr(self, "_new_button", None), "disabled" if archived else "normal"),
                                  (getattr(self, "_save_button", None), "disabled" if archived else "normal"),
                                  (getattr(self, "_archive_button", None), "disabled" if archived else "normal"),
                                  (getattr(self, "_restore_button", None), "normal" if archived else "disabled")):
                if widget is not None:
                    widget.config(state=state)
        finally:
            self._suspend_dirty = was_suspended

    def _values(self):
        is_archived = False
        if self._selected_id:
            item = next((r for r in self._rows if r["rule_id"] == self._selected_id), None)
            if item: is_archived = item.get("is_archived", False)
        return {
            "display_name": self._vars["display_name"].get().strip(),
            "condition_field": self._get_internal(self._vars["condition_field"].get(), self.CONDITION_FIELDS),
            "condition_operator": self._get_internal(self._vars["condition_operator"].get(), self.OPERATORS) or None,
            "condition_value": self._vars["condition_value"].get().strip() or None,
            "adjustment_direction": self._get_internal(self._vars["adjustment_direction"].get(), self.DIRECTIONS) or "income",
            "adjustment_type": self._get_internal(self._vars["adjustment_type"].get(), self.TYPES) or "fixed",
            "adjustment_value": self._vars["adjustment_value"].get().strip() or 0,
            "currency": self._get_internal(self._vars["currency"].get(), self.CURRENCIES) or "USD",
            "percentage_base": self._get_internal(self._vars["percentage_base"].get(), self.PERCENTAGE_BASES) or None,
            "is_enabled": self._enabled.get(), "is_archived": is_archived,
            "description": self._vars["description"].get().strip(),
        }

    def _save(self):
        # 归档规则不能直接保存
        if self._selected_id:
            item = next((r for r in self._rows if r["rule_id"] == self._selected_id), None)
            if item and item.get("is_archived"):
                messagebox.showwarning("提示", "已归档规则无法编辑，请先点击「恢复」。", parent=self)
                return
        if not self._save_internal(): return

    def _archive(self):
        if not self._selected_id: return
        if not self._check_dirty("归档/删除"): return
        item = next((r for r in self._rows if r["rule_id"] == self._selected_id), None)
        name = item["display_name"] if item else self._selected_id
        if not messagebox.askyesno("确认", f"确定要归档或删除规则「{name}」吗？", parent=self): return
        try: self._manager.archive_or_delete(self._selected_id)
        except Exception as e: messagebox.showerror("错误", str(e), parent=self); return
        self._selected_id = None; self._dirty = False; self._new(); self._refresh()

    def _restore(self):
        if not self._selected_id: return
        if not self._check_dirty("恢复"): return
        item = next((r for r in self._rows if r["rule_id"] == self._selected_id), None)
        name = item["display_name"] if item else self._selected_id
        if not messagebox.askyesno("确认", f"确定要恢复规则「{name}」吗？恢复后默认为停用状态。", parent=self): return
        try: self._manager.restore(self._selected_id)
        except Exception as e: messagebox.showerror("错误", str(e), parent=self); return
        self._refresh(); self._load_current(); self._dirty = False; self._update_status()

    def _try_close(self):
        if self._check_dirty("关闭"):
            self.destroy()


class SettingsDialog(tk.Toplevel):
    """全局设置和动态货代管理。"""

    def __init__(self, parent, config_manager, on_save=None):
        super().__init__(parent)
        self._cfg = config_manager
        self._on_save = on_save
        self.title("设置")
        self.geometry("820x720")
        self.minsize(720, 560)
        self.resizable(True, True)
        self._forwarders = ForwarderManager(config_manager._db)
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        global_box = ttk.LabelFrame(outer, text="全局设置", padding=10)
        global_box.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(global_box, text="汇率 (1 USD = ? RMB)：").grid(row=0, column=0, sticky=tk.W, pady=3)
        self._var_rate = tk.StringVar()
        ttk.Entry(global_box, textvariable=self._var_rate, width=12).grid(row=0, column=1, sticky=tk.W, pady=3)

        ttk.Label(global_box, text="默认尾程费用 (元)：").grid(row=0, column=2, sticky=tk.W, padx=(28, 0), pady=3)
        self._var_tail = tk.StringVar()
        ttk.Entry(global_box, textvariable=self._var_tail, width=12).grid(row=0, column=3, sticky=tk.W, pady=3)

        self._route_tabs = ttk.Notebook(outer)
        self._route_tabs.pack(fill=tk.BOTH, expand=True)
        self._active_tab = ttk.Frame(self._route_tabs)
        self._archived_tab = ttk.Frame(self._route_tabs)
        self._route_tabs.add(self._active_tab, text="使用中的货代")
        self._route_tabs.add(self._archived_tab, text="已归档")

        self._active_canvas, self._active_inner = self._build_scroll_area(self._active_tab)
        self._archived_canvas, self._archived_inner = self._build_scroll_area(self._archived_tab)
        self._route_vars = {}

        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="保存", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="利润调整规则...", command=self._open_profit_rules).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="新增货代", command=self._add_route).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            btn_frame,
            text="归档/删除/恢复会立即生效；其他费率修改需点击“保存”。",
            foreground="#666666",
        ).pack(side=tk.RIGHT, padx=5)
        self._render_routes()

    def _build_scroll_area(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, padding=8)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda _event, target=canvas: target.configure(scrollregion=target.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event, target=canvas, item=window: target.itemconfigure(item, width=event.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind(
            "<Enter>",
            lambda _event, target=canvas: self.bind_all(
                "<MouseWheel>",
                lambda event: target.yview_scroll(int(-1 * (event.delta / 120)), "units"),
            ),
        )
        canvas.bind("<Leave>", lambda _event: self.unbind_all("<MouseWheel>"))
        return canvas, inner

    @staticmethod
    def _clear_children(frame):
        for child in frame.winfo_children():
            child.destroy()

    def _render_routes(self):
        self._clear_children(self._active_inner)
        self._clear_children(self._archived_inner)
        self._route_vars = {}

        headers = ("名称", "头程单价(元/kg)", "固定服务费(元)", "体积重除数", "启用", "操作")
        widths = (18, 14, 14, 12)
        for column, label in enumerate(headers):
            ttk.Label(self._active_inner, text=label, font=("", 9, "bold")).grid(
                row=0, column=column, sticky=tk.W, padx=4, pady=(0, 6)
            )

        active_routes = self._cfg.get_all_routes(include_archived=False)
        if not active_routes:
            ttk.Label(self._active_inner, text="暂无货代，请点击“新增货代”。").grid(
                row=1, column=0, columnspan=6, sticky=tk.W, padx=4, pady=12
            )
        for row_index, route in enumerate(active_routes, start=1):
            vars_ = {
                key: tk.StringVar(value=str(route[key]))
                for key in ("display_name", "head_haul_rate", "fixed_service_fee", "volume_divisor")
            }
            vars_["is_enabled"] = tk.BooleanVar(value=bool(route["is_enabled"]))
            for column, key in enumerate(
                ("display_name", "head_haul_rate", "fixed_service_fee", "volume_divisor")
            ):
                ttk.Entry(
                    self._active_inner,
                    textvariable=vars_[key],
                    width=widths[column],
                ).grid(row=row_index, column=column, sticky=tk.EW, padx=4, pady=4)
            ttk.Checkbutton(
                self._active_inner, variable=vars_["is_enabled"]
            ).grid(row=row_index, column=4, padx=8, pady=4)
            ttk.Button(
                self._active_inner,
                text="归档/删除",
                command=lambda route_id=route["route_id"]: self._archive_or_delete(route_id),
            ).grid(row=row_index, column=5, padx=4, pady=4)
            self._route_vars[route["route_id"]] = vars_

        archived_routes = [
            route for route in self._cfg.get_all_routes(include_archived=True)
            if route["is_archived"]
        ]
        archive_headers = ("名称", "头程单价", "固定服务费", "体积重除数", "状态", "操作")
        for column, label in enumerate(archive_headers):
            ttk.Label(self._archived_inner, text=label, font=("", 9, "bold")).grid(
                row=0, column=column, sticky=tk.W, padx=6, pady=(0, 6)
            )
        if not archived_routes:
            ttk.Label(self._archived_inner, text="暂无已归档货代。").grid(
                row=1, column=0, columnspan=6, sticky=tk.W, padx=6, pady=12
            )
        for row_index, route in enumerate(archived_routes, start=1):
            values = (
                route["display_name"],
                f"{route['head_haul_rate']:.2f}",
                f"{route['fixed_service_fee']:.2f}",
                f"{route['volume_divisor']:.2f}",
                "已归档",
            )
            for column, value in enumerate(values):
                ttk.Label(self._archived_inner, text=value).grid(
                    row=row_index, column=column, sticky=tk.W, padx=6, pady=5
                )
            ttk.Button(
                self._archived_inner,
                text="恢复",
                command=lambda route_id=route["route_id"]: self._restore_route(route_id),
            ).grid(row=row_index, column=5, padx=6, pady=5)

        self._route_tabs.tab(0, text=f"使用中的货代 ({len(active_routes)})")
        self._route_tabs.tab(1, text=f"已归档 ({len(archived_routes)})")

    def _load_values(self):
        self._var_rate.set(str(self._cfg.exchange_rate))
        self._var_tail.set(str(self._cfg.default_tail_haul))

    def _reload_persisted_values(self):
        """Discard edits by rebuilding every editable value from the database."""
        self._load_values()
        self._render_routes()

    def _open_profit_rules(self):
        if self._confirm_refresh_with_unsaved_changes():
            ProfitRulesDialog(self, self._cfg, on_change=self._on_save)

    def _has_unsaved_changes(self):
        """Compare editable widgets with persisted settings without mutating them."""
        if not hasattr(self, "_var_rate") or not hasattr(self, "_route_vars"):
            return False
        if self._var_rate.get().strip() != str(self._cfg.exchange_rate):
            return True
        if self._var_tail.get().strip() != str(self._cfg.default_tail_haul):
            return True
        for route_id, vars_ in self._route_vars.items():
            route = self._cfg.get_route_rates(route_id)
            if route is None:
                return True
            for key in ("display_name", "head_haul_rate", "fixed_service_fee", "volume_divisor"):
                if vars_[key].get().strip() != str(route[key]):
                    return True
            if bool(vars_["is_enabled"].get()) != bool(route["is_enabled"]):
                return True
        return False

    def _confirm_refresh_with_unsaved_changes(self):
        if not self._has_unsaved_changes():
            return True
        choice = messagebox.askyesnocancel(
            "存在未保存修改",
            "当前设置有未保存修改。\n是：保存并继续；否：放弃修改并继续；取消：留在当前页面。",
            parent=self,
            default="cancel",
        )
        if choice is None:
            return False
        if choice:
            return self._save(close_after=False)
        self._reload_persisted_values()
        return True

    def _save(self, close_after=True):
        try:
            rate = float(self._var_rate.get())
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError("汇率必须是大于 0 的有限数字")
            tail = float(self._var_tail.get())
            if not math.isfinite(tail) or tail < 0:
                raise ValueError("尾程费用必须是大于等于 0 的有限数字")
            if not hasattr(self, "_route_vars"):
                self._cfg.exchange_rate = rate; self._cfg.default_tail_haul = tail
                if self._on_save: self._on_save()
                messagebox.showinfo("提示", "设置已保存。")
                if close_after:
                    self.destroy()
                return True
            routes = []
            enabled_names = []
            for route_id, vars_ in self._route_vars.items():
                name = vars_["display_name"].get().strip()
                head = float(vars_["head_haul_rate"].get())
                fixed = float(vars_["fixed_service_fee"].get())
                divisor = float(vars_["volume_divisor"].get())
                enabled = bool(vars_["is_enabled"].get())
                if not name or len(name) > 30:
                    raise ValueError("货代名称不能为空且最多30字符")
                if not all(math.isfinite(v) for v in (head, fixed, divisor)) or head <= 0 or fixed < 0 or divisor <= 0: raise ValueError(f"货代 {name} 规则无效")
                if enabled:
                    enabled_names.append(name.casefold())
                routes.append({"route_id": route_id, "display_name": name, "head_haul_rate": head, "fixed_service_fee": fixed, "volume_divisor": divisor, "is_enabled": enabled})
            if len(enabled_names) != len(set(enabled_names)): raise ValueError("启用货代名称不能重复")
            self._cfg.save_settings_and_routes(rate, tail, routes)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("输入错误", str(exc), parent=self)
            return False
        if self._on_save:
            self._on_save()
        messagebox.showinfo("提示", "设置已保存。", parent=self)
        if close_after:
            self.destroy()
        return True

    def _add_route(self):
        if not self._confirm_refresh_with_unsaved_changes():
            return
        name = simpledialog.askstring("新增货代", "货代名称：", parent=self)
        if name is None:
            return
        try:
            self._forwarders.create({"display_name": name, "head_haul_rate": 80,
                                     "fixed_service_fee": 0, "volume_divisor": 8000,
                                     "is_enabled": True})
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc), parent=self); return
        if self._on_save:
            self._on_save()
        self._render_routes()
        self._route_tabs.select(self._active_tab)
        self._active_canvas.yview_moveto(1.0)
        messagebox.showinfo(
            "新增完成",
            "货代已新增，默认规则为 80 元/kg、固定服务费 0 元、体积重除数 8000。\n"
            "可在列表中修改后点击“保存”。",
            parent=self,
        )

    def _archive_or_delete(self, route_id):
        if not self._confirm_refresh_with_unsaved_changes():
            return
        route = self._cfg.get_route_rates(route_id)
        if route is None:
            messagebox.showerror("操作失败", "货代不存在。", parent=self)
            self._render_routes()
            return
        referenced = self._forwarders.is_referenced(route_id)
        action = "归档" if referenced else "永久删除"
        detail = (
            "该货代已被历史商品引用，将停用并归档，历史记录不受影响。"
            if referenced
            else "该货代未被任何商品引用，将被永久删除。"
        )
        if not messagebox.askyesno(
            f"确认{action}",
            f"确定要{action}货代「{route['display_name']}」吗？\n{detail}\n"
            "列表会刷新。",
            parent=self,
        ):
            return
        try:
            result = self._forwarders.archive_or_delete(route_id)
        except ValueError as exc:
            messagebox.showerror("操作失败", str(exc), parent=self)
            return
        if self._on_save:
            self._on_save()
        self._render_routes()
        messagebox.showinfo(
            "操作完成",
            "货代已归档。" if result == "archived" else "货代已永久删除。",
            parent=self,
        )

    def _restore_route(self, route_id):
        if not self._confirm_refresh_with_unsaved_changes():
            return
        route = self._cfg.get_route_rates(route_id)
        if route is None:
            messagebox.showerror("操作失败", "货代不存在。", parent=self)
            self._render_routes()
            return
        if not messagebox.askyesno(
            "确认恢复",
            f"确定恢复货代「{route['display_name']}」吗？\n"
            "恢复后默认保持停用，请在“使用中的货代”页勾选启用并保存。",
            parent=self,
        ):
            return
        try:
            self._forwarders.restore(route_id)
        except ValueError as exc:
            messagebox.showerror("操作失败", str(exc), parent=self)
            return
        if self._on_save:
            self._on_save()
        self._render_routes()
        self._route_tabs.select(self._active_tab)
        messagebox.showinfo("操作完成", "货代已恢复，当前为停用状态。", parent=self)


class MainWindow:
    """应用程序主窗口"""

    def __init__(self, db_manager, config_manager):
        self._db = db_manager
        self._cfg = config_manager

        self._root = tk.Tk()
        self._root.title("微智能商品利润管理 v0.1")
        self._root.geometry("1050x700")
        self._root.minsize(900, 600)

        # 菜单栏
        self._build_menu()

        # 标签页
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill=tk.BOTH, expand=True)

        # 新商品测算页面
        self._product_page = ProductPage(self._notebook, self._db, self._cfg)
        self._notebook.add(self._product_page, text="新商品测算")

        # 历史记录页面
        self._history_page = HistoryPage(
            self._notebook, self._db, on_open_product=self._open_product_from_history
        )
        self._notebook.add(self._history_page, text="历史记录")

        # 切换到历史记录标签时自动刷新
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_menu(self):
        menubar = tk.Menu(self._root)
        self._root.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="汇率与费用设置...", command=self._open_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="备份全部数据...", command=self._backup_data)
        settings_menu.add_command(label="从备份恢复...", command=self._restore_data)
        menubar.add_cascade(label="设置", menu=settings_menu)

    def _open_settings(self):
        SettingsDialog(self._root, self._cfg, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        """设置保存后刷新计算"""
        self._product_page._refresh_route_choices()
        self._product_page._refresh_profit_rule_choices()
        self._product_page.recalculate()

    def _backup_data(self):
        initial_dir = os.path.dirname(os.path.abspath(self._db.db_path))
        initial_name = "profit_accounting_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
        destination = filedialog.asksaveasfilename(
            parent=self._root,
            title="备份全部数据",
            initialdir=initial_dir,
            initialfile=initial_name,
            defaultextension=".db",
            filetypes=[("数据库备份", "*.db"), ("所有文件", "*.*")],
        )
        if not destination:
            return
        try:
            saved_path = self._db.backup_to(destination)
        except Exception as exc:
            messagebox.showerror("备份失败", str(exc), parent=self._root)
            return
        messagebox.showinfo(
            "备份完成",
            f"商品、历史快照和全部设置已备份到：\n{saved_path}",
            parent=self._root,
        )

    def _restore_data(self):
        initial_dir = os.path.dirname(os.path.abspath(self._db.db_path))
        source = filedialog.askopenfilename(
            parent=self._root,
            title="选择数据库备份",
            initialdir=initial_dir,
            filetypes=[("数据库备份", "*.db"), ("所有文件", "*.*")],
        )
        if not source:
            return
        if not messagebox.askyesno(
            "确认恢复",
            "恢复会用所选备份替换当前商品、历史快照和全部设置。\n"
            "软件会先自动备份当前数据。确定继续吗？",
            parent=self._root,
        ):
            return
        try:
            safety_path = self._db.restore_from(source)
            self._product_page.new_product()
            self._product_page._refresh_route_choices()
            self._history_page.refresh_list()
        except Exception as exc:
            messagebox.showerror("恢复失败", str(exc), parent=self._root)
            return
        messagebox.showinfo(
            "恢复完成",
            f"已恢复所选备份。\n恢复前的数据已自动保存到：\n{safety_path}",
            parent=self._root,
        )

    def _open_product_from_history(self, product_id):
        """从历史记录打开商品"""
        self._product_page.load_product(product_id)
        self._notebook.select(0)  # 切换到新商品测算页面

    def _on_tab_changed(self, event):
        """标签页切换时刷新历史列表"""
        current_tab = self._notebook.index(self._notebook.select())
        if current_tab == 1:  # 历史记录标签
            self._history_page.refresh_list()

    def run(self):
        """启动主循环"""
        self._root.mainloop()
