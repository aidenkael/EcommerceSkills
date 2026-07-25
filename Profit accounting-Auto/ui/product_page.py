"""
新商品测算页面

包含全部输入字段、实时计算结果、操作按钮。
支持售价/利润率双向联动，通过 last_modified 追踪避免循环。
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# 确保可以导入同级模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculation import (
    volumetric_weight,
    chargeable_weight,
    head_haul_cost,
    total_logistics_cost,
    total_cost,
    profit_amount,
    profit_rate,
    suggested_price_from_rate,
    rmb_to_usd,
    usd_to_rmb,
)


def _safe_float(val):
    """安全转为 float，失败返回 None"""
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class ProductPage(ttk.Frame):
    """新商品测算页面"""

    def __init__(self, parent, db_manager, config_manager):
        super().__init__(parent)
        self._db = db_manager
        self._cfg = config_manager
        self._product_id = None  # 当前编辑的商品ID
        self._last_modified = None  # 用户最后修改的关键字段
        self._programmatic = False  # 标记程序化更新
        self._has_snapshot = False  # 是否有快照可还原
        self._calculated = {}       # 存储计算中间值，供保存时使用

        self._build_ui()
        self.new_product()

    # ─── UI 构建 ─────────────────────────────────────────

    def _build_ui(self):
        """构建界面"""
        # 主容器：左侧输入 + 右侧结果
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧：输入区域（可滚动）
        left = ttk.Frame(paned)
        paned.add(left, weight=3)

        canvas = tk.Canvas(left, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canvas.yview)
        self._input_frame = ttk.Frame(canvas)
        self._input_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._input_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 右侧：结果显示
        right = ttk.Frame(paned)
        paned.add(right, weight=2)
        self._build_results(right)

        # 底部按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="新建", command=self.new_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="保存", command=self.save_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="还原", command=self.restore_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清空", command=self.clear_form).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="计算结果", command=self.recalculate).pack(side=tk.LEFT, padx=2)

        # 构建输入字段
        self._build_inputs()

    def _make_entry(self, parent, label, row, col=1, default=""):
        """创建标签+输入框"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        var = tk.StringVar(value=default)
        entry = ttk.Entry(parent, textvariable=var, width=22)
        entry.grid(row=row, column=col, sticky=tk.EW, padx=5, pady=2)
        return var, entry

    def _make_section(self, parent, title, row_start):
        """创建分区标题"""
        ttk.Label(parent, text=title, font=("", 10, "bold")).grid(
            row=row_start, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10, 2)
        )

    def _build_inputs(self):
        """构建所有输入字段"""
        pf = self._input_frame
        r = 0

        # ── 基本信息 ──
        self._make_section(pf, "基本信息", r); r += 1
        self._var_name, _ = self._make_entry(pf, "商品名称：", r); r += 1
        self._var_cost, entry_cost = self._make_entry(pf, "商品成本 (元)：", r); r += 1
        self._var_domestic, _ = self._make_entry(pf, "发往义乌运费 (元)：", r); r += 1

        # ── 裸件数据 ──
        self._make_section(pf, "裸件数据", r); r += 1
        self._var_net_w, _ = self._make_entry(pf, "裸重 (kg)：", r); r += 1
        self._var_net_l, _ = self._make_entry(pf, "裸长 (cm)：", r); r += 1
        self._var_net_wi, _ = self._make_entry(pf, "裸宽 (cm)：", r); r += 1
        self._var_net_h, _ = self._make_entry(pf, "裸高 (cm)：", r); r += 1

        # ── 包装数据 ──
        self._make_section(pf, "包装数据（手动填写）", r); r += 1
        self._var_pkg_w, _ = self._make_entry(pf, "包装后重量 (kg)：", r); r += 1
        self._var_pkg_l, _ = self._make_entry(pf, "包装后长 (cm)：", r); r += 1
        self._var_pkg_wi, _ = self._make_entry(pf, "包装后宽 (cm)：", r); r += 1
        self._var_pkg_h, _ = self._make_entry(pf, "包装后高 (cm)：", r); r += 1

        # ── 物流费用 ──
        self._make_section(pf, "物流费用", r); r += 1
        self._var_fixed_fee, _ = self._make_entry(
            pf, "固定服务费 (元)：", r, default=str(self._cfg.fixed_service_fee)
        ); r += 1
        self._var_tail_haul, _ = self._make_entry(
            pf, "尾程费用 (元)：", r, default=str(self._cfg.default_tail_haul)
        ); r += 1

        # ── 售价与利润 ──
        self._make_section(pf, "售价与利润", r); r += 1
        self._var_shein, _ = self._make_entry(pf, "SHEIN二次核价 (元)：", r); r += 1
        self._var_price_rmb, entry_rmb = self._make_entry(pf, "当前售价人民币 (元)：", r); r += 1
        self._var_price_usd, entry_usd = self._make_entry(pf, "当前售价美元 ($)：", r); r += 1
        self._var_target_rate, entry_rate = self._make_entry(pf, "目标利润率 (%)：", r); r += 1
        self._var_promo_rate, entry_promo = self._make_entry(pf, "推广预留比例 (%)：", r); r += 1

        # ── 备注 ──
        self._make_section(pf, "备注", r); r += 1
        self._var_notes = tk.StringVar()
        ttk.Entry(pf, textvariable=self._var_notes, width=46).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=2
        ); r += 1

        # 展开列
        pf.columnconfigure(1, weight=1)

        # ── trace 绑定：关键字段修改时实时计算 ──
        for var in [self._var_cost, self._var_domestic,
                     self._var_net_w, self._var_net_l, self._var_net_wi, self._var_net_h,
                     self._var_pkg_w, self._var_pkg_l, self._var_pkg_wi, self._var_pkg_h,
                     self._var_fixed_fee, self._var_tail_haul]:
            var.trace_add("write", lambda *_: self._on_field_changed("cost"))

        self._var_price_rmb.trace_add("write", lambda *_: self._on_field_changed("price_rmb"))
        self._var_price_usd.trace_add("write", lambda *_: self._on_field_changed("price_usd"))
        self._var_target_rate.trace_add("write", lambda *_: self._on_field_changed("target_rate"))
        self._var_promo_rate.trace_add("write", lambda *_: self._on_field_changed("promo_rate"))
        self._var_shein.trace_add("write", lambda *_: self._on_field_changed("cost"))

    def _build_results(self, parent):
        """构建右侧计算结果区域"""
        ttk.Label(parent, text="计算结果", font=("", 11, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 10))

        self._result_labels = {}
        result_fields = [
            ("vol_weight", "体积重 (kg)："),
            ("charge_weight", "计费重量 (kg)："),
            ("head_haul", "头程费用 (元)："),
            ("total_logistics", "总物流成本 (元)："),
            ("total_cost", "总成本 (元)："),
            ("profit", "利润金额 (元)："),
            ("profit_rate", "利润率 (%)："),
            ("suggested_price", "建议售价 (元)："),
            ("converted_usd", "折合美元 ($)："),
        ]

        for key, label in result_fields:
            frm = ttk.Frame(parent)
            frm.pack(fill=tk.X, padx=5, pady=2)
            ttk.Label(frm, text=label, width=16).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            lbl = ttk.Label(frm, textvariable=var, font=("", 10, "bold"))
            lbl.pack(side=tk.LEFT)
            self._result_labels[key] = var

    # ─── 事件处理 ─────────────────────────────────────────

    def _on_field_changed(self, field_type):
        """输入字段变更回调"""
        if self._programmatic:
            return

        if field_type in ("price_rmb", "price_usd", "target_rate", "promo_rate"):
            self._last_modified = field_type

        self.recalculate()

    def recalculate(self):
        """执行全部计算并更新显示"""
        self._programmatic = True
        try:
            self._do_recalculate()
        finally:
            self._programmatic = False

    def _do_recalculate(self):
        """核心计算逻辑"""
        # 读取输入
        cost = _safe_float(self._var_cost.get())
        domestic = _safe_float(self._var_domestic.get())
        pkg_w = _safe_float(self._var_pkg_w.get())
        pkg_l = _safe_float(self._var_pkg_l.get())
        pkg_wi = _safe_float(self._var_pkg_wi.get())
        pkg_h = _safe_float(self._var_pkg_h.get())
        fixed_fee = _safe_float(self._var_fixed_fee.get())
        tail_haul = _safe_float(self._var_tail_haul.get())
        price_rmb = _safe_float(self._var_price_rmb.get())
        target_rate = _safe_float(self._var_target_rate.get())
        promo_rate = _safe_float(self._var_promo_rate.get())
        exchange_rate = self._cfg.exchange_rate

        # 1. 体积重
        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        self._set_result("vol_weight", vol_w, " kg")
        self._calculated["vol_weight"] = vol_w

        # 2. 计费重量
        chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("charge_weight", chg_w, " kg")
        self._calculated["charge_weight"] = chg_w

        # 3. 头程费用
        head_rate = self._cfg.head_haul_rate
        head_cost = head_haul_cost(chg_w, head_rate)
        self._set_result("head_haul", head_cost, " 元")
        self._calculated["head_haul"] = head_cost

        # 4. 总物流成本
        logistics = total_logistics_cost(head_cost, fixed_fee, tail_haul)
        self._set_result("total_logistics", logistics, " 元")
        self._calculated["total_logistics"] = logistics

        # 5. 总成本
        tc = total_cost(cost, domestic, logistics)
        self._set_result("total_cost", tc, " 元")
        self._calculated["total_cost"] = tc

        # 6-9. 利润/售价双向联动
        if self._last_modified in ("target_rate",) and target_rate is not None and tc is not None:
            # 用户最后改了目标利润率 → 反算建议售价
            suggested = suggested_price_from_rate(tc, target_rate, promo_rate or 0)
            self._set_result("suggested_price", suggested, " 元")
            if suggested is not None:
                self._var_price_rmb.set(f"{suggested:.2f}")
                self._update_usd_from_rmb(suggested)

            # 从建议售价算利润
            p_val = profit_amount(suggested, tc) if suggested else None
            self._set_result("profit", p_val, " 元")
            pr = profit_rate(suggested, tc) if suggested else None
            self._set_result("profit_rate", pr, " %")

        elif self._last_modified in ("price_rmb", "price_usd") or (
            self._last_modified is None and price_rmb is not None
        ):
            # 用户最后改了售价 → 算利润和利润率
            # 先处理 USD → RMB 的情况
            if self._last_modified == "price_usd":
                price_usd = _safe_float(self._var_price_usd.get())
                if price_usd is not None and exchange_rate > 0:
                    price_rmb = price_usd * exchange_rate
                    self._var_price_rmb.set(f"{price_rmb:.2f}")

            p_val = profit_amount(price_rmb, tc) if price_rmb is not None else None
            self._set_result("profit", p_val, " 元")
            pr = profit_rate(price_rmb, tc) if price_rmb is not None else None
            self._set_result("profit_rate", pr, " %")

            # 更新美元价格
            self._update_usd_from_rmb(price_rmb)

            # 清空建议售价
            self._set_result("suggested_price", None)

        else:
            # 没有明确方向，清空利润和价格结果
            self._set_result("profit", None)
            self._set_result("profit_rate", None)
            self._set_result("suggested_price", None)

    def _update_usd_from_rmb(self, rmb_val):
        """根据人民币价格更新美元价格"""
        if rmb_val is not None:
            usd = rmb_to_usd(rmb_val, self._cfg.exchange_rate)
            self._set_result("converted_usd", usd, " $")
            if usd is not None:
                self._var_price_usd.set(f"{usd:.2f}")
        else:
            self._set_result("converted_usd", None)

    def _set_result(self, key, value, suffix=""):
        """设置结果显示"""
        var = self._result_labels.get(key)
        if var is None:
            return
        if value is None:
            var.set("数据不足")
        else:
            var.set(f"{value:.2f}{suffix}")

    # ─── 按钮操作 ─────────────────────────────────────────

    def new_product(self):
        """新建商品"""
        self._product_id = None
        self._has_snapshot = False
        self._last_modified = None
        self.clear_form()

    def clear_form(self):
        """清空表单"""
        self._programmatic = True
        try:
            for var in [
                self._var_name, self._var_cost, self._var_domestic,
                self._var_net_w, self._var_net_l, self._var_net_wi, self._var_net_h,
                self._var_pkg_w, self._var_pkg_l, self._var_pkg_wi, self._var_pkg_h,
                self._var_shein, self._var_price_rmb, self._var_price_usd,
                self._var_target_rate, self._var_promo_rate, self._var_notes,
            ]:
                var.set("")
            self._var_fixed_fee.set(str(self._cfg.fixed_service_fee))
            self._var_tail_haul.set(str(self._cfg.default_tail_haul))

            for key in self._result_labels:
                self._result_labels[key].set("—")
            self._calculated = {}

            self._last_modified = None
        finally:
            self._programmatic = False

    def save_product(self):
        """保存商品"""
        data = self._gather_data()
        if not data.get("name", "").strip():
            messagebox.showwarning("提示", "请至少填写商品名称后再保存。")
            return

        if self._product_id:
            # 更新已有商品
            self._db.update_product(self._product_id, data)
            messagebox.showinfo("提示", f"商品 {self._product_id} 已更新。")
        else:
            # 新建商品
            self._product_id = self._db.create_product(data)
            # 保存第一次快照
            self._db.save_snapshot(self._product_id, data)
            self._has_snapshot = True
            messagebox.showinfo("提示", f"商品已保存，ID: {self._product_id}")

    def restore_product(self):
        """还原到第一次保存的快照"""
        if not self._product_id:
            messagebox.showinfo("提示", "当前商品尚未保存，无法还原。")
            return

        snap = self._db.get_snapshot(self._product_id)
        if not snap:
            messagebox.showinfo("提示", "没有可还原的快照。")
            return

        self._load_data(snap)
        messagebox.showinfo("提示", "已还原到首次保存的状态。")

    def load_product(self, product_id: str):
        """从数据库加载商品"""
        product = self._db.get_product(product_id)
        if not product:
            messagebox.showerror("错误", f"未找到商品: {product_id}")
            return

        self._product_id = product_id
        snap = self._db.get_snapshot(product_id)
        self._has_snapshot = snap is not None
        self._last_modified = None
        self._load_data(product)

    def _gather_data(self) -> dict:
        """收集当前表单数据"""
        return {
            "name": self._var_name.get(),
            "cost": _safe_float(self._var_cost.get()),
            "domestic_shipping": _safe_float(self._var_domestic.get()),
            "net_weight": _safe_float(self._var_net_w.get()),
            "net_length": _safe_float(self._var_net_l.get()),
            "net_width": _safe_float(self._var_net_wi.get()),
            "net_height": _safe_float(self._var_net_h.get()),
            "packaged_weight": _safe_float(self._var_pkg_w.get()),
            "packaged_length": _safe_float(self._var_pkg_l.get()),
            "packaged_width": _safe_float(self._var_pkg_wi.get()),
            "packaged_height": _safe_float(self._var_pkg_h.get()),
            "head_haul_cost": self._calculated.get("head_haul"),
            "fixed_service_fee": _safe_float(self._var_fixed_fee.get()),
            "tail_haul_cost": _safe_float(self._var_tail_haul.get()),
            "shein_price": _safe_float(self._var_shein.get()),
            "selling_price_rmb": _safe_float(self._var_price_rmb.get()),
            "selling_price_usd": _safe_float(self._var_price_usd.get()),
            "target_profit_rate": _safe_float(self._var_target_rate.get()),
            "promotion_reserve_rate": _safe_float(self._var_promo_rate.get()),
            "notes": self._var_notes.get(),
        }

    def _load_data(self, data: dict):
        """加载数据到表单"""
        self._programmatic = True
        try:
            self._var_name.set(data.get("name", "") or "")
            self._var_cost.set(self._fmt(data.get("cost")))
            self._var_domestic.set(self._fmt(data.get("domestic_shipping")))
            self._var_net_w.set(self._fmt(data.get("net_weight")))
            self._var_net_l.set(self._fmt(data.get("net_length")))
            self._var_net_wi.set(self._fmt(data.get("net_width")))
            self._var_net_h.set(self._fmt(data.get("net_height")))
            self._var_pkg_w.set(self._fmt(data.get("packaged_weight")))
            self._var_pkg_l.set(self._fmt(data.get("packaged_length")))
            self._var_pkg_wi.set(self._fmt(data.get("packaged_width")))
            self._var_pkg_h.set(self._fmt(data.get("packaged_height")))
            self._var_shein.set(self._fmt(data.get("shein_price")))
            self._var_price_rmb.set(self._fmt(data.get("selling_price_rmb")))
            self._var_price_usd.set(self._fmt(data.get("selling_price_usd")))
            self._var_target_rate.set(self._fmt(data.get("target_profit_rate")))
            self._var_promo_rate.set(self._fmt(data.get("promotion_reserve_rate")))

            ff = data.get("fixed_service_fee")
            self._var_fixed_fee.set(self._fmt(ff, self._cfg.fixed_service_fee))
            th = data.get("tail_haul_cost")
            self._var_tail_haul.set(self._fmt(th, self._cfg.default_tail_haul))

            self._var_notes.set(data.get("notes", "") or "")
        finally:
            self._programmatic = False

        self.recalculate()

    @staticmethod
    def _fmt(val, default=""):
        """格式化数值为空或浮点字符串"""
        if val is None:
            return str(default) if default else ""
        try:
            return f"{float(val):.2f}"
        except (ValueError, TypeError):
            return str(val)

    # ─── 公开属性 ─────────────────────────────────────────

    @property
    def product_id(self):
        return self._product_id
