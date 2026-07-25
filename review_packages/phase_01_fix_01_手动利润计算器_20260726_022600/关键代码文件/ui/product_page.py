"""
新商品测算页面

P0修复版本：
- P0-2: 缺失关键费用时标记"部分数据不足/估算"，不按0生成虚假利润
- P0-3: _calc_direction 独立追踪计算方向，推广比例变化不丢失方向
- P0-4: 目标利润率只更新"建议售价"标签，不覆盖当前售价输入框
- P0-5: 加载历史商品时显示保存时的数据，不自动用当前费率重算
- P0-6: 清空时清除 _product_id，防止误覆盖旧记录
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

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
        self._product_id = None
        self._calc_direction = None    # "price" 或 "rate"
        self._programmatic = False
        self._has_snapshot = False
        self._historical_mode = False   # 浏览历史记录模式
        self._snapshot_rules = {}       # 保存时的费率快照
        self._calculated = {}           # 计算结果原始值
        self._partial = {}              # 结果是否部分缺失

        self._build_ui()
        self.new_product()

    # ─── UI 构建 ─────────────────────────────────────────

    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧输入
        left = ttk.Frame(paned)
        paned.add(left, weight=3)
        canvas = tk.Canvas(left, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canvas.yview)
        self._input_frame = ttk.Frame(canvas)
        self._input_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._input_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # 右侧结果
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        # 费率提示条（加载历史记录时显示）
        self._rate_notice_var = tk.StringVar()
        self._rate_notice_label = ttk.Label(
            right, textvariable=self._rate_notice_var,
            foreground="#cc6600", font=("", 9, "italic")
        )
        self._build_results(right)

        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="新建", command=self.new_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="保存", command=self.save_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="还原", command=self.restore_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清空", command=self.clear_form).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="用当前费率重算", command=self._force_recalc).pack(side=tk.LEFT, padx=2)

        self._build_inputs()

    def _make_entry(self, parent, label, row, col=1, default=""):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        var = tk.StringVar(value=default)
        entry = ttk.Entry(parent, textvariable=var, width=22)
        entry.grid(row=row, column=col, sticky=tk.EW, padx=5, pady=2)
        return var, entry

    def _make_section(self, parent, title, row_start):
        ttk.Label(parent, text=title, font=("", 10, "bold")).grid(
            row=row_start, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10, 2))

    def _build_inputs(self):
        pf = self._input_frame
        r = 0

        self._make_section(pf, "基本信息", r); r += 1
        self._var_name, _ = self._make_entry(pf, "商品名称：", r); r += 1
        self._var_cost, _ = self._make_entry(pf, "商品成本 (元)：", r); r += 1
        self._var_domestic, _ = self._make_entry(pf, "发往义乌运费 (元)：", r); r += 1

        self._make_section(pf, "裸件数据", r); r += 1
        self._var_net_w, _ = self._make_entry(pf, "裸重 (kg)：", r); r += 1
        self._var_net_l, _ = self._make_entry(pf, "裸长 (cm)：", r); r += 1
        self._var_net_wi, _ = self._make_entry(pf, "裸宽 (cm)：", r); r += 1
        self._var_net_h, _ = self._make_entry(pf, "裸高 (cm)：", r); r += 1

        self._make_section(pf, "包装数据（手动填写）", r); r += 1
        self._var_pkg_w, _ = self._make_entry(pf, "包装后重量 (kg)：", r); r += 1
        self._var_pkg_l, _ = self._make_entry(pf, "包装后长 (cm)：", r); r += 1
        self._var_pkg_wi, _ = self._make_entry(pf, "包装后宽 (cm)：", r); r += 1
        self._var_pkg_h, _ = self._make_entry(pf, "包装后高 (cm)：", r); r += 1

        self._make_section(pf, "物流费用", r); r += 1
        self._var_fixed_fee, _ = self._make_entry(pf, "固定服务费 (元)：", r, default=str(self._cfg.fixed_service_fee)); r += 1
        self._var_tail_haul, _ = self._make_entry(pf, "尾程费用 (元)：", r, default=str(self._cfg.default_tail_haul)); r += 1

        self._make_section(pf, "售价与利润", r); r += 1
        self._var_shein, _ = self._make_entry(pf, "SHEIN二次核价 (元)：", r); r += 1
        self._var_price_rmb, _ = self._make_entry(pf, "当前售价人民币 (元)：", r); r += 1
        self._var_price_usd, _ = self._make_entry(pf, "当前售价美元 ($)：", r); r += 1
        self._var_target_rate, _ = self._make_entry(pf, "目标利润率 (%)：", r); r += 1
        self._var_promo_rate, _ = self._make_entry(pf, "推广预留比例 (%)：", r); r += 1

        self._make_section(pf, "备注", r); r += 1
        self._var_notes = tk.StringVar()
        ttk.Entry(pf, textvariable=self._var_notes, width=46).grid(row=r, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=2); r += 1
        pf.columnconfigure(1, weight=1)

        # trace 绑定
        for var in [self._var_cost, self._var_domestic,
                     self._var_net_w, self._var_net_l, self._var_net_wi, self._var_net_h,
                     self._var_pkg_w, self._var_pkg_l, self._var_pkg_wi, self._var_pkg_h,
                     self._var_fixed_fee, self._var_tail_haul, self._var_shein]:
            var.trace_add("write", lambda *_: self._on_field_changed("cost"))

        self._var_price_rmb.trace_add("write", lambda *_: self._on_field_changed("price_rmb"))
        self._var_price_usd.trace_add("write", lambda *_: self._on_field_changed("price_usd"))
        self._var_target_rate.trace_add("write", lambda *_: self._on_field_changed("target_rate"))
        self._var_promo_rate.trace_add("write", lambda *_: self._on_field_changed("promo_rate"))

    def _build_results(self, parent):
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
        if self._programmatic:
            return

        if field_type in ("price_rmb", "price_usd"):
            self._calc_direction = "price"
        elif field_type == "target_rate":
            self._calc_direction = "rate"
        # promo_rate 不改变方向，但触发重算

        # 退出历史模式
        if self._historical_mode:
            self._historical_mode = False
            self._show_rate_notice(None)

        self.recalculate()

    def recalculate(self):
        self._programmatic = True
        try:
            self._do_recalculate()
        finally:
            self._programmatic = False

    def _force_recalc(self):
        """「用当前费率重算」按钮：强制退出历史模式并重算"""
        self._historical_mode = False
        self._show_rate_notice(None)
        self.recalculate()

    def _do_recalculate(self):
        """核心计算"""
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
        self._set_result("vol_weight", vol_w, " kg", partial=(vol_w is None and any(v is not None for v in [pkg_l, pkg_wi, pkg_h])))
        self._calculated["vol_weight"] = vol_w

        # 2. 计费重量
        chg_w = chargeable_weight(pkg_w, vol_w)
        chg_partial = chg_w is None and (pkg_w is not None or vol_w is not None)
        self._set_result("charge_weight", chg_w, " kg", partial=chg_partial)
        self._calculated["charge_weight"] = chg_w

        # 3. 头程费用
        head_rate = self._cfg.head_haul_rate
        head_cost = head_haul_cost(chg_w, head_rate)
        head_partial = head_cost is None and chg_partial
        self._set_result("head_haul", head_cost, " 元", partial=head_partial)
        self._calculated["head_haul"] = head_cost
        self._partial["head_haul"] = head_partial

        # 4. 总物流成本
        logistics = total_logistics_cost(head_cost, fixed_fee, tail_haul)
        log_partial = head_partial  # 头程缺失→物流成本不完整
        self._set_result("total_logistics", logistics, " 元", partial=log_partial)
        self._calculated["total_logistics"] = logistics
        self._partial["total_logistics"] = log_partial

        # 5. 总成本
        tc = total_cost(cost, domestic, logistics)
        self._set_result("total_cost", tc, " 元", partial=log_partial)
        self._calculated["total_cost"] = tc
        self._partial["total_cost"] = log_partial

        # 6-9. 利润 / 售价联动
        if log_partial:
            # 物流费用不完整，利润不可靠
            self._set_result("profit", None, suffix=" 元", partial=True)
            self._set_result("profit_rate", None, suffix=" %", partial=True)
            self._set_result("suggested_price", None, suffix=" 元")
            self._set_result("converted_usd", None, suffix=" $")
            self._calculated["profit"] = None
            self._calculated["profit_rate"] = None
            self._calculated["suggested_price"] = None
            return

        # 根据计算方向：
        if self._calc_direction == "rate" and target_rate is not None and tc is not None:
            # 方向=利润率 → 反算建议售价（不覆盖用户当前售价）
            suggested = suggested_price_from_rate(tc, target_rate, promo_rate or 0)
            self._set_result("suggested_price", suggested, " 元")
            self._calculated["suggested_price"] = suggested

            # 不设置 _var_price_rmb！只显示建议售价
            if suggested is not None:
                usd_suggested = rmb_to_usd(suggested, exchange_rate)
                self._set_result("converted_usd", usd_suggested, " $")

            # 如果用户有填售价，仍计算实际利润
            if price_rmb is not None:
                p_val = profit_amount(price_rmb, tc)
                self._set_result("profit", p_val, " 元")
                self._calculated["profit"] = p_val
                pr = profit_rate(price_rmb, tc)
                self._set_result("profit_rate", pr, " %")
                self._calculated["profit_rate"] = pr
                usd = rmb_to_usd(price_rmb, exchange_rate)
                self._set_result("converted_usd", usd, " $")
                if usd is not None:
                    self._var_price_usd.set(f"{usd:.2f}")
            else:
                self._set_result("profit", None, " 元")
                self._set_result("profit_rate", None, " %")

        elif self._calc_direction == "price" or (self._calc_direction is None and price_rmb is not None):
            # 方向=售价 → 算利润
            if self._calc_direction is None and self._last_was_rate():
                # 如果之前是按利润率方向，且用户还没改过售价，保持利润率方向
                pass
            else:
                # 处理 USD→RMB
                if self._calc_direction == "price":
                    # 检查是 RMB 还是 USD 触发
                    pass  # 由调用方处理

                p_val = profit_amount(price_rmb, tc) if price_rmb is not None else None
                self._set_result("profit", p_val, " 元")
                self._calculated["profit"] = p_val
                pr = profit_rate(price_rmb, tc) if price_rmb is not None else None
                self._set_result("profit_rate", pr, " %")
                self._calculated["profit_rate"] = pr

                # 更新美元
                usd = rmb_to_usd(price_rmb, exchange_rate)
                self._set_result("converted_usd", usd, " $")
                self._calculated["converted_usd"] = usd
                if usd is not None:
                    self._var_price_usd.set(f"{usd:.2f}")

                # 清空建议售价
                self._set_result("suggested_price", None)
                self._calculated["suggested_price"] = None

        elif self._calc_direction == "rate" and (target_rate is None or tc is None):
            # 方向是利润率但数据不全
            self._set_result("suggested_price", None, " 元")
            if price_rmb is not None:
                p_val = profit_amount(price_rmb, tc)
                self._set_result("profit", p_val, " 元")
                self._calculated["profit"] = p_val
                pr = profit_rate(price_rmb, tc)
                self._set_result("profit_rate", pr, " %")
                self._calculated["profit_rate"] = pr
        else:
            # 没有明确方向且没有售价
            self._set_result("profit", None, " 元")
            self._set_result("profit_rate", None, " %")
            self._set_result("suggested_price", None, " 元")
            self._set_result("converted_usd", None, " $")
            self._calculated["profit"] = None
            self._calculated["profit_rate"] = None
            self._calculated["suggested_price"] = None

    def _last_was_rate(self):
        """检查当前输入是否暗示利润率方向"""
        # 如果目标利润率有值但售价为空，判断为利润率方向
        return (_safe_float(self._var_target_rate.get()) is not None
                and _safe_float(self._var_price_rmb.get()) is None)

    def _set_result(self, key, value, suffix="", partial=False):
        var = self._result_labels.get(key)
        if var is None:
            return
        if value is None:
            if partial:
                var.set(f"数据不足(物流费用不完整)")
            else:
                var.set("数据不足")
        elif partial:
            var.set(f"≥{value:.2f}{suffix}(估算)")
        else:
            var.set(f"{value:.2f}{suffix}")

    def _show_rate_notice(self, rules_diff):
        """显示/隐藏费率变更提示"""
        if rules_diff:
            lines = []
            if 'exchange_rate' in rules_diff:
                lines.append(f"汇率: {rules_diff['exchange_rate'][0]:.2f}→{rules_diff['exchange_rate'][1]:.2f}")
            if 'head_haul_rate' in rules_diff:
                lines.append(f"头程: {rules_diff['head_haul_rate'][0]:.0f}→{rules_diff['head_haul_rate'][1]:.0f}元/kg")
            if 'fixed_service_fee' in rules_diff:
                lines.append(f"固定费: {rules_diff['fixed_service_fee'][0]:.0f}→{rules_diff['fixed_service_fee'][1]:.0f}元")
            self._rate_notice_var.set("历史记录 | 费率已变更: " + ", ".join(lines) + " | 点击「用当前费率重算」更新")
            self._rate_notice_label.pack(before=self._result_labels["vol_weight"].master.master, fill=tk.X, padx=5, pady=(0, 5))
        else:
            self._rate_notice_var.set("")
            self._rate_notice_label.pack_forget()

    # ─── 按钮操作 ─────────────────────────────────────────

    def new_product(self):
        self._product_id = None
        self._has_snapshot = False
        self._calc_direction = None
        self._historical_mode = False
        self._show_rate_notice(None)
        self.clear_form()

    def clear_form(self):
        """清空表单（同时清除 product_id，防误覆盖）"""
        self._product_id = None          # ← P0-6 修复
        self._has_snapshot = False
        self._historical_mode = False
        self._show_rate_notice(None)
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
            self._partial = {}
            self._calc_direction = None
        finally:
            self._programmatic = False

    def save_product(self):
        data = self._gather_data()

        if self._product_id:
            self._db.update_product(self._product_id, data)
            self._historical_mode = False
            self._show_rate_notice(None)
            messagebox.showinfo("提示", f"商品 {self._product_id} 已更新。")
        else:
            self._product_id = self._db.create_product(data)
            # 保存快照（含当前费率规则）
            rules = {
                "exchange_rate": self._cfg.exchange_rate,
                "head_haul_rate": self._cfg.head_haul_rate,
                "fixed_service_fee": self._cfg.fixed_service_fee,
            }
            self._db.save_snapshot(self._product_id, data, rules)
            self._has_snapshot = True
            self._historical_mode = False
            self._show_rate_notice(None)
            messagebox.showinfo("提示", f"商品已保存，ID: {self._product_id}")

    def restore_product(self):
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
        """从数据库加载商品（P0-5：使用保存时的值，不自动重算）"""
        product = self._db.get_product(product_id)
        if not product:
            messagebox.showerror("错误", f"未找到商品: {product_id}")
            return

        self._product_id = product_id
        self._has_snapshot = self._db.get_snapshot(product_id) is not None
        self._historical_mode = True
        self._calc_direction = None

        # 加载表单数据
        self._load_data(product)

        # 从数据库取值填充计算结果（不重算！）
        self._calculated = {
            "head_haul": product.get("head_haul_cost"),
            "total_logistics": None,  # 不从DB直接读，由UI层显示
            "total_cost": None,
            "profit": None,
            "profit_rate": None,
            "suggested_price": None,
            "converted_usd": product.get("selling_price_usd"),
        }

        # 检查费率是否变更
        self._check_rate_changes()

    def _check_rate_changes(self):
        """对比快照费率与当前费率"""
        if not self._product_id:
            return
        snap = self._db.get_snapshot(self._product_id)
        if not snap:
            return

        changes = {}
        snap_rate = snap.get("_snapshot_exchange_rate")
        if snap_rate is not None and abs(snap_rate - self._cfg.exchange_rate) > 0.001:
            changes["exchange_rate"] = (snap_rate, self._cfg.exchange_rate)
        snap_head = snap.get("_snapshot_head_haul_rate")
        if snap_head is not None and abs(snap_head - self._cfg.head_haul_rate) > 0.001:
            changes["head_haul_rate"] = (snap_head, self._cfg.head_haul_rate)
        snap_fixed = snap.get("_snapshot_fixed_service_fee")
        if snap_fixed is not None and abs(snap_fixed - self._cfg.fixed_service_fee) > 0.001:
            changes["fixed_service_fee"] = (snap_fixed, self._cfg.fixed_service_fee)

        if changes:
            self._show_rate_notice(changes)
        else:
            self._show_rate_notice(None)

    def _gather_data(self) -> dict:
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

    @staticmethod
    def _fmt(val, default=""):
        if val is None:
            return str(default) if default else ""
        try:
            return f"{float(val):.2f}"
        except (ValueError, TypeError):
            return str(val)

    @property
    def product_id(self):
        return self._product_id
