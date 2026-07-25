"""
历史记录页面

P1修复版：
- "利润率"列显示实际利润率（售价-总成本相关），非目标利润率
- "成本"列改为"采购成本"
- 支持外部触发刷新
"""

import tkinter as tk
from tkinter import ttk, messagebox

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class HistoryPage(ttk.Frame):
    """历史记录管理页面"""

    def __init__(self, parent, db_manager, on_open_product=None):
        super().__init__(parent)
        self._db = db_manager
        self._on_open = on_open_product

        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text="搜索：").pack(side=tk.LEFT, padx=(0, 5))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        ttk.Entry(search_frame, textvariable=self._search_var, width=30).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(search_frame, text="刷新", command=self.refresh_list).pack(side=tk.LEFT)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("id", "name", "purchase_cost", "price", "actual_rate", "updated")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("id", text="商品ID")
        self._tree.heading("name", text="名称")
        self._tree.heading("purchase_cost", text="采购成本(元)")
        self._tree.heading("price", text="售价(元)")
        self._tree.heading("actual_rate", text="实际利润率(%)")
        self._tree.heading("updated", text="更新时间")

        self._tree.column("id", width=80)
        self._tree.column("name", width=150)
        self._tree.column("purchase_cost", width=90, anchor=tk.E)
        self._tree.column("price", width=80, anchor=tk.E)
        self._tree.column("actual_rate", width=95, anchor=tk.E)
        self._tree.column("updated", width=150)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<Double-1>", lambda e: self._open_selected())

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="打开", command=self._open_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除", command=self._delete_selected).pack(side=tk.LEFT, padx=2)

    def refresh_list(self):
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

            # fix_02-7: 实际净利润率 = (售价 - 完整总成本 - 推广预留) / 售价
            if price_val is not None and price_val > 0:
                domestic = p.get("domestic_shipping") or 0
                head = p.get("head_haul_cost") or 0
                fixed = p.get("fixed_service_fee") or 0
                tail = p.get("tail_haul_cost") or 0
                total_c = (cost_val or 0) + domestic + head + fixed + tail
                promo = p.get("promotion_reserve_rate") or 0
                # 净利润 = 售价 - 总成本 - 推广费用
                net_p = price_val - total_c - price_val * (promo / 100)
                rate = (net_p / price_val) * 100
                rate_str = f"{rate:.1f}%"
            else:
                rate_str = ""

            updated = p.get("updated_at", "")[:19]

            self._tree.insert(
                "", tk.END, iid=pid,
                values=(pid, name, cost_str, price_str, rate_str, updated)
            )

    def _on_search(self):
        self.refresh_list()

    def _open_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条记录。")
            return
        pid = sel[0]
        if self._on_open:
            self._on_open(pid)

    def _delete_selected(self):
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
