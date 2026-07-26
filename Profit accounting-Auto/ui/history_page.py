"""
历史记录页面 — fix_03

新增：货代列、物流不完整时利润率不显示、净利润率使用完整总成本
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculation import total_logistics_cost, total_cost, net_profit_rate


def saved_or_legacy_net_rate(product):
    """优先返回保存结果；仅在全部成本完整时兼容计算旧记录。"""
    calculated = product.get("_current_calculation_results")
    if isinstance(calculated, dict) and "net_profit_rate" in calculated:
        return calculated.get("net_profit_rate")

    required = [
        product.get("cost"),
        product.get("domestic_shipping"),
        product.get("head_haul_cost"),
        product.get("fixed_service_fee"),
        product.get("tail_haul_cost"),
        product.get("selling_price_rmb"),
    ]
    if any(value is None for value in required):
        return None
    logistics = total_logistics_cost(
        product["head_haul_cost"],
        product["fixed_service_fee"],
        product["tail_haul_cost"],
    )
    total = total_cost(product["cost"], product["domestic_shipping"], logistics)
    return net_profit_rate(
        product["selling_price_rmb"],
        total,
        product.get("promotion_reserve_rate"),
    )


class HistoryPage(ttk.Frame):

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
        columns = ("id", "name", "forwarder", "purchase_cost", "price", "net_rate", "updated")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self._tree.heading("id", text="ID")
        self._tree.heading("name", text="名称")
        self._tree.heading("forwarder", text="货代")
        self._tree.heading("purchase_cost", text="采购成本")
        self._tree.heading("price", text="售价")
        self._tree.heading("net_rate", text="净利率")
        self._tree.heading("updated", text="更新时间")
        self._tree.column("id", width=70)
        self._tree.column("name", width=120)
        self._tree.column("forwarder", width=60)
        self._tree.column("purchase_cost", width=70, anchor=tk.E)
        self._tree.column("price", width=70, anchor=tk.E)
        self._tree.column("net_rate", width=70, anchor=tk.E)
        self._tree.column("updated", width=130)

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
            rules = p.get("_current_rule_snapshot") or {}
            fwd = p.get("freight_forwarder")
            fwd_str = rules.get("route_display_name") or (self._db.get_route_rates(fwd) or {}).get("display_name") or fwd or "未知"

            cost_val = p.get("cost")
            cost_str = f"{cost_val:.2f}" if cost_val is not None else ""
            price_val = p.get("selling_price_rmb")
            price_str = f"{price_val:.2f}" if price_val is not None else ""

            rate = saved_or_legacy_net_rate(p)
            if rate is not None:
                rate_str = f"{rate:.1f}%"
            elif price_val is not None and price_val > 0:
                rate_str = "数据不足"
            else:
                rate_str = ""

            updated = p.get("updated_at", "")[:19]
            self._tree.insert("", tk.END, iid=pid,
                              values=(pid, name, fwd_str, cost_str, price_str, rate_str, updated))

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
