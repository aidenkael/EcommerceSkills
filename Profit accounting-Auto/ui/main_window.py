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
