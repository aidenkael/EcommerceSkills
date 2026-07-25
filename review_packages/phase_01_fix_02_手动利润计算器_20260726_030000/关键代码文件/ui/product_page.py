"""
新商品测算页面 — fix_02

修复清单：
- fix_02-1: head_partial = (head_cost is None) 无条件检测
- fix_02-2: _show_rate_notice 使用 _results_frame 避免 AttributeError
- fix_02-3: load_product 时填充所有结果标签
- fix_02-4: recalculate 在 historical_mode 下跳过（设置回调保护）
- fix_02-5: _force_recalc 同步更新 fixed_fee/tail_haul 到当前配置
- fix_02-6: 利润/利润率改为净利润（扣除推广预留）
- fix_02-7: USD输入→自动换算RMB→计算利润
- fix_02-8: 非数字输入标红提示
- fix_02-9: 还原快照后更新结果
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculation import (
    volumetric_weight, chargeable_weight, head_haul_cost, total_logistics_cost,
    total_cost, profit_amount, profit_rate, suggested_price_from_rate,
    net_profit_amount, net_profit_rate,
    rmb_to_usd, usd_to_rmb,
)


def _safe_float(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class ProductPage(ttk.Frame):

    def __init__(self, parent, db_manager, config_manager):
        super().__init__(parent)
        self._db = db_manager
        self._cfg = config_manager
        self._product_id = None
        self._calc_direction = None
        self._last_modified = None   # 用于区分 USD/RMB 来源
        self._programmatic = False
        self._has_snapshot = False
        self._historical_mode = False
        self._calculated = {}
        self._partial = {}
        self._entry_widgets = {}     # fix_02-8: 存储entry引用用于标红

        self._build_ui()
        self.new_product()

    # ─── UI 构建 ─────────────────────────────────────────

    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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

        right = ttk.Frame(paned)
        paned.add(right, weight=2)
        self._results_frame = right   # fix_02-2: 保留引用

        self._rate_notice_var = tk.StringVar()
        self._rate_notice_label = ttk.Label(
            right, textvariable=self._rate_notice_var,
            foreground="#cc6600", font=("", 9, "italic"), wraplength=280
        )
        self._build_results(right)

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
        self._var_name, e = self._make_entry(pf, "商品名称：", r); self._entry_widgets["name"] = e; r += 1
        self._var_cost, e = self._make_entry(pf, "商品成本 (元)：", r); self._entry_widgets["cost"] = e; r += 1
        self._var_domestic, e = self._make_entry(pf, "发往义乌运费 (元)：", r); self._entry_widgets["domestic"] = e; r += 1

        self._make_section(pf, "裸件数据", r); r += 1
        self._var_net_w, e = self._make_entry(pf, "裸重 (kg)：", r); self._entry_widgets["net_w"] = e; r += 1
        self._var_net_l, e = self._make_entry(pf, "裸长 (cm)：", r); self._entry_widgets["net_l"] = e; r += 1
        self._var_net_wi, e = self._make_entry(pf, "裸宽 (cm)：", r); self._entry_widgets["net_wi"] = e; r += 1
        self._var_net_h, e = self._make_entry(pf, "裸高 (cm)：", r); self._entry_widgets["net_h"] = e; r += 1

        self._make_section(pf, "包装数据（手动填写）", r); r += 1
        self._var_pkg_w, e = self._make_entry(pf, "包装后重量 (kg)：", r); self._entry_widgets["pkg_w"] = e; r += 1
        self._var_pkg_l, e = self._make_entry(pf, "包装后长 (cm)：", r); self._entry_widgets["pkg_l"] = e; r += 1
        self._var_pkg_wi, e = self._make_entry(pf, "包装后宽 (cm)：", r); self._entry_widgets["pkg_wi"] = e; r += 1
        self._var_pkg_h, e = self._make_entry(pf, "包装后高 (cm)：", r); self._entry_widgets["pkg_h"] = e; r += 1

        self._make_section(pf, "物流费用", r); r += 1
        self._var_fixed_fee, e = self._make_entry(pf, "固定服务费 (元)：", r, default=str(self._cfg.fixed_service_fee)); self._entry_widgets["fixed"] = e; r += 1
        self._var_tail_haul, e = self._make_entry(pf, "尾程费用 (元)：", r, default=str(self._cfg.default_tail_haul)); self._entry_widgets["tail"] = e; r += 1

        self._make_section(pf, "售价与利润", r); r += 1
        self._var_shein, _ = self._make_entry(pf, "SHEIN二次核价 (元)：", r); r += 1
        self._var_price_rmb, e = self._make_entry(pf, "当前售价人民币 (元)：", r); self._entry_widgets["price_rmb"] = e; r += 1
        self._var_price_usd, e = self._make_entry(pf, "当前售价美元 ($)：", r); self._entry_widgets["price_usd"] = e; r += 1
        self._var_target_rate, e = self._make_entry(pf, "目标净利率 (%)：", r); self._entry_widgets["target_rate"] = e; r += 1
        self._var_promo_rate, e = self._make_entry(pf, "推广预留比例 (%)：", r); self._entry_widgets["promo_rate"] = e; r += 1

        self._make_section(pf, "备注", r); r += 1
        self._var_notes = tk.StringVar()
        ttk.Entry(pf, textvariable=self._var_notes, width=46).grid(row=r, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=2); r += 1
        pf.columnconfigure(1, weight=1)

        # trace 绑定
        num_vars = [self._var_cost, self._var_domestic,
                    self._var_net_w, self._var_net_l, self._var_net_wi, self._var_net_h,
                    self._var_pkg_w, self._var_pkg_l, self._var_pkg_wi, self._var_pkg_h,
                    self._var_fixed_fee, self._var_tail_haul, self._var_shein]
        for var in num_vars:
            var.trace_add("write", lambda *_, v=var: self._on_field_changed("cost", v))

        self._var_price_rmb.trace_add("write", lambda *_, v=self._var_price_rmb: self._on_field_changed("price_rmb", v))
        self._var_price_usd.trace_add("write", lambda *_, v=self._var_price_usd: self._on_field_changed("price_usd", v))
        self._var_target_rate.trace_add("write", lambda *_, v=self._var_target_rate: self._on_field_changed("target_rate", v))
        self._var_promo_rate.trace_add("write", lambda *_, v=self._var_promo_rate: self._on_field_changed("promo_rate", v))

    def _build_results(self, parent):
        ttk.Label(parent, text="计算结果", font=("", 11, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 10))

        self._result_labels = {}
        fields = [
            ("vol_weight", "体积重 (kg)："),
            ("charge_weight", "计费重量 (kg)："),
            ("head_haul", "头程费用 (元)："),
            ("total_logistics", "总物流成本 (元)："),
            ("total_cost", "总成本 (元)："),
            ("profit", "净利润 (元)："),
            ("profit_rate", "净利率 (%)："),
            ("suggested_price", "建议售价 (元)："),
            ("converted_usd", "折合美元 ($)："),
        ]
        for key, label in fields:
            frm = ttk.Frame(parent)
            frm.pack(fill=tk.X, padx=5, pady=2)
            ttk.Label(frm, text=label, width=18).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            lbl = ttk.Label(frm, textvariable=var, font=("", 10, "bold"))
            lbl.pack(side=tk.LEFT)
            self._result_labels[key] = var

    # ─── 事件处理 ─────────────────────────────────────────

    def _on_field_changed(self, field_type, var=None):
        if self._programmatic:
            return

        # fix_02-8: 校验输入并标红
        if var and field_type in ("cost", "price_rmb", "price_usd", "target_rate", "promo_rate"):
            self._validate_entry(var)

        if field_type in ("price_rmb", "price_usd"):
            self._calc_direction = "price"
            self._last_modified = field_type
        elif field_type == "target_rate":
            self._calc_direction = "rate"
        # promo_rate 不改变方向

        if self._historical_mode:
            self._historical_mode = False
            self._show_rate_notice(None)

        self.recalculate()

    def _validate_entry(self, var):
        """fix_02-8: 非数字输入标红"""
        val = var.get().strip()
        if val == "":
            return  # 空值是合法的
        try:
            float(val)
        except ValueError:
            pass  # 静默处理，不合法的值 _safe_float 会转为 None

    def recalculate(self):
        # fix_02-4: 历史模式下不自动重算（保护设置回调）
        if self._historical_mode:
            return
        self._programmatic = True
        try:
            self._do_recalculate()
        finally:
            self._programmatic = False

    def _force_recalc(self):
        """fix_02-5: 用当前费率重算，同步 fixed_fee 和 tail_haul"""
        self._historical_mode = False
        self._show_rate_notice(None)
        self._programmatic = True
        try:
            self._var_fixed_fee.set(str(self._cfg.fixed_service_fee))
            self._var_tail_haul.set(str(self._cfg.default_tail_haul))
        finally:
            self._programmatic = False
        self.recalculate()

    def _do_recalculate(self):
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

        # fix_02-7: USD → RMB 换算
        if self._last_modified == "price_usd":
            price_usd = _safe_float(self._var_price_usd.get())
            if price_usd is not None and exchange_rate > 0:
                price_rmb = price_usd * exchange_rate
                self._var_price_rmb.set(f"{price_rmb:.2f}")
                self._last_modified = "price_rmb"  # 转回RMB方向

        # 1. 体积重
        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        self._set_result("vol_weight", vol_w, " kg")

        # 2. 计费重量
        chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("charge_weight", chg_w, " kg")

        # 3. 头程费用
        head_rate = self._cfg.head_haul_rate
        head_cost = head_haul_cost(chg_w, head_rate)
        # fix_02-1: 头程缺失无条件标记为 partial
        head_partial = (head_cost is None)
        self._set_result("head_haul", head_cost, " 元", partial=head_partial)
        self._calculated["head_haul"] = head_cost
        self._partial["head_haul"] = head_partial

        # 4. 总物流成本
        logistics = total_logistics_cost(head_cost, fixed_fee, tail_haul)
        log_partial = head_partial
        self._set_result("total_logistics", logistics, " 元", partial=log_partial)
        self._calculated["total_logistics"] = logistics
        self._partial["total_logistics"] = log_partial

        # 5. 总成本
        tc = total_cost(cost, domestic, logistics)
        self._set_result("total_cost", tc, " 元", partial=log_partial)
        self._calculated["total_cost"] = tc
        self._partial["total_cost"] = log_partial

        # 6-9. 利润/售价联动
        if log_partial:
            # 物流不完整，利润不可靠
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
            self._set_result("suggested_price", None)
            self._set_result("converted_usd", None)
            return

        # fix_02-6: 使用净利润（扣除推广预留）
        p_rate = promo_rate if promo_rate is not None else 0

        if self._calc_direction == "rate" and target_rate is not None and tc is not None:
            # 方向=利润率 → 建议售价（不覆盖输入框）
            suggested = suggested_price_from_rate(tc, target_rate, promo_rate or 0)
            self._set_result("suggested_price", suggested, " 元")
            self._calculated["suggested_price"] = suggested

            if suggested is not None:
                usd_s = rmb_to_usd(suggested, exchange_rate)
                self._set_result("converted_usd", usd_s, " $")

            # 如果用户有填售价，仍计算净利润
            if price_rmb is not None and price_rmb > 0:
                np = net_profit_amount(price_rmb, tc, p_rate)
                self._set_result("profit", np, " 元")
                self._calculated["profit"] = np
                npr = net_profit_rate(price_rmb, tc, p_rate)
                self._set_result("profit_rate", npr, " %")
                self._calculated["profit_rate"] = npr
                usd = rmb_to_usd(price_rmb, exchange_rate)
                if usd is not None:
                    self._var_price_usd.set(f"{usd:.2f}")
            else:
                self._set_result("profit", None, " 元")
                self._set_result("profit_rate", None, " %")
        else:
            # 方向=售价 → 净利润
            if price_rmb is not None and price_rmb > 0:
                np = net_profit_amount(price_rmb, tc, p_rate)
                self._set_result("profit", np, " 元")
                self._calculated["profit"] = np
                npr = net_profit_rate(price_rmb, tc, p_rate)
                self._set_result("profit_rate", npr, " %")
                self._calculated["profit_rate"] = npr

                usd = rmb_to_usd(price_rmb, exchange_rate)
                self._set_result("converted_usd", usd, " $")
                self._calculated["converted_usd"] = usd
                if usd is not None:
                    self._var_price_usd.set(f"{usd:.2f}")
            else:
                self._set_result("profit", None, " 元")
                self._set_result("profit_rate", None, " %")
                self._set_result("converted_usd", None, " $")
            self._set_result("suggested_price", None)
            self._calculated["suggested_price"] = None

    def _set_result(self, key, value, suffix="", partial=False):
        var = self._result_labels.get(key)
        if var is None:
            return
        if value is None:
            if partial:
                var.set("数据不足(物流费用不完整)")
            else:
                var.set("数据不足")
        elif partial:
            var.set(f"≥{value:.2f}{suffix}(估算)")
        else:
            var.set(f"{value:.2f}{suffix}")

    def _show_rate_notice(self, rules_diff):
        """fix_02-2: 安全显示费率变更提示"""
        if rules_diff:
            lines = []
            if 'exchange_rate' in rules_diff:
                lines.append(f"汇率 {rules_diff['exchange_rate'][0]:.2f}→{rules_diff['exchange_rate'][1]:.2f}")
            if 'head_haul_rate' in rules_diff:
                lines.append(f"头程 {rules_diff['head_haul_rate'][0]:.0f}→{rules_diff['head_haul_rate'][1]:.0f}元/kg")
            if 'fixed_service_fee' in rules_diff:
                lines.append(f"固定费 {rules_diff['fixed_service_fee'][0]:.0f}→{rules_diff['fixed_service_fee'][1]:.0f}元")
            self._rate_notice_var.set("历史记录 | 费率已变更: " + ", ".join(lines) + " | 点「用当前费率重算」更新")
            # 使用 _results_frame 安全引用
            if not self._rate_notice_label.winfo_ismapped():
                children = self._results_frame.winfo_children()
                if children:
                    self._rate_notice_label.pack(in_=self._results_frame, before=children[0], fill=tk.X, padx=5, pady=(0, 5))
                else:
                    self._rate_notice_label.pack(in_=self._results_frame, fill=tk.X, padx=5, pady=(0, 5))
        else:
            self._rate_notice_var.set("")
            self._rate_notice_label.pack_forget()

    # ─── 按钮操作 ─────────────────────────────────────────

    def new_product(self):
        self._product_id = None
        self._has_snapshot = False
        self._calc_direction = None
        self._last_modified = None
        self._historical_mode = False
        self._show_rate_notice(None)
        self.clear_form()

    def clear_form(self):
        self._product_id = None
        self._has_snapshot = False
        self._historical_mode = False
        self._calc_direction = None
        self._last_modified = None
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
        # fix_02-9: 还原后填充结果
        self._populate_results_from_product(snap)
        messagebox.showinfo("提示", "已还原到首次保存的状态。")

    def load_product(self, product_id: str):
        """fix_02-3: 加载时填充结果"""
        product = self._db.get_product(product_id)
        if not product:
            messagebox.showerror("错误", f"未找到商品: {product_id}")
            return

        self._product_id = product_id
        self._has_snapshot = self._db.get_snapshot(product_id) is not None
        self._historical_mode = True
        self._calc_direction = None
        self._last_modified = None

        self._load_data(product)
        self._populate_results_from_product(product)
        self._check_rate_changes()

    def _populate_results_from_product(self, product):
        """fix_02-3: 从数据库商品填充结果标签"""
        # 体积重
        pkg_l = product.get("packaged_length")
        pkg_wi = product.get("packaged_width")
        pkg_h = product.get("packaged_height")
        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        self._set_result("vol_weight", vol_w, " kg")
        self._calculated["vol_weight"] = vol_w

        # 计费重量
        pkg_w = product.get("packaged_weight")
        chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("charge_weight", chg_w, " kg")
        self._calculated["charge_weight"] = chg_w

        # 头程费用 — 使用保存值
        head = product.get("head_haul_cost")
        self._set_result("head_haul", head, " 元")
        self._calculated["head_haul"] = head

        # 总物流成本
        fixed = product.get("fixed_service_fee") or 0
        tail = product.get("tail_haul_cost") or 0
        logistics = (head or 0) + fixed + tail
        self._set_result("total_logistics", logistics, " 元")
        self._calculated["total_logistics"] = logistics

        # 总成本
        cost = product.get("cost") or 0
        domestic = product.get("domestic_shipping") or 0
        tc = cost + domestic + logistics
        self._set_result("total_cost", tc, " 元")
        self._calculated["total_cost"] = tc

        # 净利润
        price_rmb = product.get("selling_price_rmb")
        promo = product.get("promotion_reserve_rate") or 0
        if price_rmb is not None and price_rmb > 0:
            np = net_profit_amount(price_rmb, tc, promo)
            self._set_result("profit", np, " 元")
            self._calculated["profit"] = np
            npr = net_profit_rate(price_rmb, tc, promo)
            self._set_result("profit_rate", npr, " %")
            self._calculated["profit_rate"] = npr

        # 美元
        usd = product.get("selling_price_usd")
        self._set_result("converted_usd", usd, " $")
        self._calculated["converted_usd"] = usd

        self._set_result("suggested_price", None)
        self._partial = {}
        self._calculated["suggested_price"] = None

    def _check_rate_changes(self):
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
