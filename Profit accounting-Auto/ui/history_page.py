"""
历史记录页面

支持搜索、列表查看、打开编辑、删除。
"""

import tkinter as tk
from tkinter import ttk, messagebox


class HistoryPage(ttk.Frame):
    """历史记录管理页面"""

    def __init__(self, parent, db_manager, on_open_product=None):
        super().__init__(parent)
        self._db = db_manager
        self._on_open = on_open_product  # 回调：打开商品 (product_id)

        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        """构建界面"""
        # 搜索栏
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text="搜索：").pack(side=tk.LEFT, padx=(0, 5))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(search_frame, text="刷新", command=self.refresh_list).pack(side=tk.LEFT)

        # 列表
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("id", "name", "cost", "price", "rate", "updated")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("id", text="商品ID")
        self._tree.heading("name", text="名称")
        self._tree.heading("cost", text="成本(元)")
        self._tree.heading("price", text="售价(元)")
        self._tree.heading("rate", text="利润率(%)")
        self._tree.heading("updated", text="更新时间")

        self._tree.column("id", width=80)
        self._tree.column("name", width=150)
        self._tree.column("cost", width=80, anchor=tk.E)
        self._tree.column("price", width=80, anchor=tk.E)
        self._tree.column("rate", width=80, anchor=tk.E)
        self._tree.column("updated", width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击打开
        self._tree.bind("<Double-1>", lambda e: self._open_selected())

        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="打开", command=self._open_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除", command=self._delete_selected).pack(side=tk.LEFT, padx=2)

    def refresh_list(self):
        """刷新列表"""
        for item in self._tree.get_children():
            self._tree.delete(item)

        keyword = self._search_var.get().strip()
        products = self._db.search_products(keyword=keyword, limit=200)

        for p in products:
            pid = p.get("id", "")
            name = p.get("name", "")

            cost_val = p.get("cost")
            cost_str = f"{cost_val:.2f}" if cost_val is not None else ""

            price_val = p.get("selling_price_rmb")
            price_str = f"{price_val:.2f}" if price_val is not None else ""

            rate_val = p.get("target_profit_rate")
            rate_str = f"{rate_val:.1f}%" if rate_val is not None else ""

            updated = p.get("updated_at", "")[:19]  # 截取到秒

            self._tree.insert(
                "", tk.END, iid=pid, values=(pid, name, cost_str, price_str, rate_str, updated)
            )

    def _on_search(self):
        """搜索防抖"""
        self.refresh_list()

    def _open_selected(self):
        """打开选中商品"""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条记录。")
            return
        pid = sel[0]
        if self._on_open:
            self._on_open(pid)

    def _delete_selected(self):
        """删除选中商品"""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条记录。")
            return

        pid = sel[0]
        product = self._db.get_product(pid)
        name = product.get("name", pid) if product else pid

        if not messagebox.askyesno("确认删除", f"确定要删除商品「{name}」(ID: {pid}) 吗？\n此操作不可撤销。"):
            return

        self._db.delete_product(pid)
        self.refresh_list()
        messagebox.showinfo("提示", f"商品 {pid} 已删除。")
