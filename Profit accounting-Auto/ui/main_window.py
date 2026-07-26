"""
主窗口模块

包含菜单栏、设置对话框、两个标签页（新商品测算 / 历史记录）。
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .product_page import ProductPage
from .history_page import HistoryPage


class SettingsDialog(tk.Toplevel):
    """设置对话框 — v2：仅汇率和默认尾程"""

    def __init__(self, parent, config_manager, on_save=None):
        super().__init__(parent)
        self._cfg = config_manager
        self._on_save = on_save
        self.title("设置")
        self.geometry("300x160")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        r = 0
        ttk.Label(frame, text="汇率 (1 USD = ? RMB)：").grid(row=r, column=0, sticky=tk.W, pady=5)
        self._var_rate = tk.StringVar()
        ttk.Entry(frame, textvariable=self._var_rate, width=12).grid(row=r, column=1, pady=5); r += 1

        ttk.Label(frame, text="默认尾程费用 (元)：").grid(row=r, column=0, sticky=tk.W, pady=5)
        self._var_tail = tk.StringVar()
        ttk.Entry(frame, textvariable=self._var_tail, width=12).grid(row=r, column=1, pady=5); r += 1

        ttk.Label(frame, text="头程/固定费由货代选择决定", foreground="gray", font=("", 8)).grid(row=r, column=0, columnspan=2, pady=5); r += 1

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=r, column=0, columnspan=2, pady=5)
        ttk.Button(btn_frame, text="保存", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def _load_values(self):
        self._var_rate.set(str(self._cfg.exchange_rate))
        self._var_tail.set(str(self._cfg.default_tail_haul))

    def _save(self):
        try:
            rate = float(self._var_rate.get())
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError("汇率必须是大于 0 的有限数字")
            tail = float(self._var_tail.get())
            if not math.isfinite(tail) or tail < 0:
                raise ValueError("尾程费用必须是大于等于 0 的有限数字")
        except ValueError as e:
            messagebox.showerror("输入错误", f"请输入有效数字：{e}")
            return
        self._cfg.exchange_rate = rate
        self._cfg.default_tail_haul = tail
        if self._on_save:
            self._on_save()
        messagebox.showinfo("提示", "设置已保存。")
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
