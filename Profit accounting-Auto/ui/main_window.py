"""
主窗口模块

包含菜单栏、设置对话框、两个标签页（新商品测算 / 历史记录）。
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .product_page import ProductPage
from .history_page import HistoryPage
from config.forwarder_manager import ForwarderManager


class SettingsDialog(tk.Toplevel):
    """全局设置和两个固定货代槽位。"""

    def __init__(self, parent, config_manager, on_save=None):
        super().__init__(parent)
        self._cfg = config_manager
        self._on_save = on_save
        self.title("设置")
        self.geometry("680x720")
        self.resizable(True, True)
        self._forwarders = ForwarderManager(config_manager._db)
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        r = 0
        ttk.Label(frame, text="全局设置", font=("", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W); r += 1
        ttk.Label(frame, text="汇率 (1 USD = ? RMB)：").grid(row=r, column=0, sticky=tk.W, pady=5)
        self._var_rate = tk.StringVar()
        ttk.Entry(frame, textvariable=self._var_rate, width=12).grid(row=r, column=1, pady=5); r += 1

        ttk.Label(frame, text="默认尾程费用 (元)：").grid(row=r, column=0, sticky=tk.W, pady=5)
        self._var_tail = tk.StringVar()
        ttk.Entry(frame, textvariable=self._var_tail, width=12).grid(row=r, column=1, pady=5); r += 1

        self._route_vars = {}
        for route in self._cfg.get_all_routes(include_archived=False):
            box = ttk.LabelFrame(frame, text=f"货代：{route['display_name']}", padding=8)
            box.grid(row=r, column=0, columnspan=2, sticky=tk.EW, pady=6); r += 1
            vars_ = {key: tk.StringVar() for key in ("display_name", "head_haul_rate", "fixed_service_fee", "volume_divisor")}
            vars_["is_enabled"] = tk.BooleanVar()
            for idx, (key, label) in enumerate((("display_name", "名称"), ("head_haul_rate", "头程单价 (元/kg)"), ("fixed_service_fee", "固定服务费 (元)"), ("volume_divisor", "体积重除数"))):
                ttk.Label(box, text=label + "：").grid(row=idx, column=0, sticky=tk.W)
                ttk.Entry(box, textvariable=vars_[key], width=20).grid(row=idx, column=1, sticky=tk.W)
            ttk.Checkbutton(box, text="启用", variable=vars_["is_enabled"]).grid(row=4, column=0, columnspan=2, sticky=tk.W)
            self._route_vars[route["route_id"]] = vars_

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=r, column=0, columnspan=2, pady=5)
        ttk.Button(btn_frame, text="保存", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="新增货代", command=self._add_route).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def _load_values(self):
        self._var_rate.set(str(self._cfg.exchange_rate))
        self._var_tail.set(str(self._cfg.default_tail_haul))
        for route in self._cfg.get_all_routes(include_archived=False):
            vars_ = self._route_vars[route["route_id"]]
            for key in ("display_name", "head_haul_rate", "fixed_service_fee", "volume_divisor"):
                vars_[key].set(str(route[key]))
            vars_["is_enabled"].set(bool(route["is_enabled"]))

    def _save(self):
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
                self.destroy(); return
            routes = []
            enabled_names = []
            for key, vars_ in self._route_vars.items():
                name = vars_["display_name"].get().strip()
                head = float(vars_["head_haul_rate"].get())
                fixed = float(vars_["fixed_service_fee"].get())
                divisor = float(vars_["volume_divisor"].get())
                enabled = bool(vars_["is_enabled"].get())
                if not name or len(name) > 30: raise ValueError(f"货代 {key} 名称不能为空且最多30字符")
                if not all(math.isfinite(v) for v in (head, fixed, divisor)) or head <= 0 or fixed < 0 or divisor <= 0: raise ValueError(f"货代 {name} 规则无效")
                if enabled: enabled_names.append(name)
                routes.append({"route_id": key, "display_name": name, "head_haul_rate": head, "fixed_service_fee": fixed, "volume_divisor": divisor, "is_enabled": enabled})
            if len(enabled_names) != len(set(enabled_names)): raise ValueError("启用货代名称不能重复")
        except ValueError as e:
            messagebox.showerror("输入错误", f"请输入有效数字：{e}")
            return
        self._cfg.save_settings_and_routes(rate, tail, routes)
        if self._on_save:
            self._on_save()
        messagebox.showinfo("提示", "设置已保存。")
        self.destroy()

    def _add_route(self):
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
        self.destroy()


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
        menubar.add_cascade(label="设置", menu=settings_menu)

    def _open_settings(self):
        SettingsDialog(self._root, self._cfg, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        """设置保存后刷新计算"""
        self._product_page._refresh_route_choices()
        self._product_page.recalculate()

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
