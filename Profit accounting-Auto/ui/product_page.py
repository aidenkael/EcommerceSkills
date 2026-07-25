"""
新商品测算页面 — fix_03

新增：货代选择、真实输入校验、完整规则快照恢复
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculation import (
    volumetric_weight, chargeable_weight, head_haul_cost, total_logistics_cost,
    total_cost, profit_amount, profit_rate, suggested_price_from_rate,
    net_profit_amount, net_profit_rate, rmb_to_usd, usd_to_rmb,
)
from config.config_manager import VOLUME_DIVISOR, FORWARDER_LABELS


def _safe_float(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _is_valid_number(s):
    """检查字符串是否为合法非负数字"""
    if s is None or str(s).strip() == "":
        return True  # 空值合法
    try:
        v = float(s)
        return v >= 0
    except (ValueError, TypeError):
        return False


class ProductPage(ttk.Frame):

    def __init__(self, parent, db_manager, config_manager):
        super().__init__(parent)
        self._db = db_manager
        self._cfg = config_manager
        self._product_id = None
        self._calc_direction = None
        self._last_modified = None
        self._programmatic = False
        self._has_snapshot = False
        self._historical_mode = False
        self._calculated = {}
        self._partial = {}
        self._entry_vars = {}     # var name → tk.StringVar
        self._entry_widgets = {}  # var name → ttk.Entry
        self._forwarder_var = None

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
        self._results_frame = right

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
        ttk.Button(btn_frame, text="用当前规则重算", command=self._force_recalc).pack(side=tk.LEFT, padx=2)

        self._build_inputs()

    def _make_number_entry(self, parent, label, row, name, default=""):
        """创建数值输入框（含校验）"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        var = tk.StringVar(value=default)
        entry = tk.Entry(parent, textvariable=var, width=22, bg="white", relief="sunken")
        entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=2)
        # 校验绑定：每次按键后检查
        var.trace_add("write", lambda *_, n=name: self._validate_field(n))
        self._entry_vars[name] = var
        self._entry_widgets[name] = entry
        return var

    def _make_text_entry(self, parent, label, row, default=""):
        """创建文本输入框"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        var = tk.StringVar(value=default)
        entry = ttk.Entry(parent, textvariable=var, width=22)
        entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=2)
        return var

    def _make_section(self, parent, title, row_start):
        ttk.Label(parent, text=title, font=("", 10, "bold")).grid(
            row=row_start, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10, 2))

    def _build_inputs(self):
        pf = self._input_frame
        r = 0

        self._make_section(pf, "基本信息", r); r += 1
        self._var_name = self._make_text_entry(pf, "商品名称：", r); r += 1
        self._var_cost = self._make_number_entry(pf, "商品成本 (元)：", r, "cost"); r += 1
        self._var_domestic = self._make_number_entry(pf, "发往义乌运费 (元)：", r, "domestic"); r += 1

        # 货代选择
        self._make_section(pf, "货代选择", r); r += 1
        fwd_frame = ttk.Frame(pf)
        fwd_frame.grid(row=r, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        ttk.Label(fwd_frame, text="货代：").pack(side=tk.LEFT)
        self._forwarder_var = tk.StringVar(value="")
        fwd_combo = ttk.Combobox(fwd_frame, textvariable=self._forwarder_var, values=["", "深圳", "义乌"], state="readonly", width=10)
        fwd_combo.pack(side=tk.LEFT, padx=5)
        fwd_combo.bind("<<ComboboxSelected>>", lambda e: self._on_forwarder_changed())
        ttk.Label(fwd_frame, text="(留空=未选择，不计算利润)", foreground="gray", font=("", 8)).pack(side=tk.LEFT, padx=5)
        r += 1

        self._make_section(pf, "裸件数据", r); r += 1
        self._var_net_w = self._make_number_entry(pf, "裸重 (kg)：", r, "net_w"); r += 1
        self._var_net_l = self._make_number_entry(pf, "裸长 (cm)：", r, "net_l"); r += 1
        self._var_net_wi = self._make_number_entry(pf, "裸宽 (cm)：", r, "net_wi"); r += 1
        self._var_net_h = self._make_number_entry(pf, "裸高 (cm)：", r, "net_h"); r += 1

        self._make_section(pf, "包装数据（手动填写）", r); r += 1
        self._var_pkg_w = self._make_number_entry(pf, "包装后重量 (kg)：", r, "pkg_w"); r += 1
        self._var_pkg_l = self._make_number_entry(pf, "包装后长 (cm)：", r, "pkg_l"); r += 1
        self._var_pkg_wi = self._make_number_entry(pf, "包装后宽 (cm)：", r, "pkg_wi"); r += 1
        self._var_pkg_h = self._make_number_entry(pf, "包装后高 (cm)：", r, "pkg_h"); r += 1

        self._make_section(pf, "物流费用", r); r += 1
        self._var_tail_haul = self._make_number_entry(pf, "尾程费用 (元)：", r, "tail", default=str(self._cfg.default_tail_haul)); r += 1

        self._make_section(pf, "售价与利润", r); r += 1
        self._var_shein = self._make_number_entry(pf, "SHEIN二次核价 (元)：", r, "shein"); r += 1
        self._var_price_rmb = self._make_number_entry(pf, "当前售价人民币 (元)：", r, "price_rmb"); r += 1
        self._var_price_usd = self._make_number_entry(pf, "当前售价美元 ($)：", r, "price_usd"); r += 1
        self._var_target_rate = self._make_number_entry(pf, "目标净利率 (%)：", r, "target_rate"); r += 1
        self._var_promo_rate = self._make_number_entry(pf, "推广预留比例 (%)：", r, "promo_rate"); r += 1

        self._make_section(pf, "备注", r); r += 1
        self._var_notes = tk.StringVar()
        ttk.Entry(pf, textvariable=self._var_notes, width=46).grid(row=r, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=2); r += 1
        pf.columnconfigure(1, weight=1)

        # trace 绑定（仅关键交互字段触发计算）
        cost_fields = ["cost", "domestic", "net_w", "net_l", "net_wi", "net_h",
                       "pkg_w", "pkg_l", "pkg_wi", "pkg_h", "tail", "shein"]
        for name in cost_fields:
            if name in self._entry_vars:
                self._entry_vars[name].trace_add("write", lambda *_, n=name: self._on_field_changed("cost"))

        if "price_rmb" in self._entry_vars:
            self._entry_vars["price_rmb"].trace_add("write", lambda *_: self._on_field_changed("price_rmb"))
        if "price_usd" in self._entry_vars:
            self._entry_vars["price_usd"].trace_add("write", lambda *_: self._on_field_changed("price_usd"))
        if "target_rate" in self._entry_vars:
            self._entry_vars["target_rate"].trace_add("write", lambda *_: self._on_field_changed("target_rate"))
        if "promo_rate" in self._entry_vars:
            self._entry_vars["promo_rate"].trace_add("write", lambda *_: self._on_field_changed("promo_rate"))

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

    # ─── 货代处理 ─────────────────────────────────────────

    def _get_forwarder_key(self):
        """将界面显示值转为数据库key"""
        label = self._forwarder_var.get()
        if label == "深圳":
            return "shenzhen"
        elif label == "义乌":
            return "yiwu"
        return None

    def _set_forwarder_key(self, key):
        label = FORWARDER_LABELS.get(key, "")
        self._forwarder_var.set(label)

    def _on_forwarder_changed(self):
        if self._programmatic:
            return
        if self._historical_mode:
            self._historical_mode = False
            self._show_rate_notice(None)
        self.recalculate()

    # ─── 输入校验 ─────────────────────────────────────────

    def _validate_field(self, name):
        """校验单个字段，非法时标红"""
        var = self._entry_vars.get(name)
        entry = self._entry_widgets.get(name)
        if not var or not entry:
            return
        val = var.get().strip()
        if val == "":
            entry.configure(bg="white")
            return
        try:
            f = float(val)
            if f < 0:
                entry.configure(bg="#ffcccc")  # 负数→红色
            else:
                entry.configure(bg="white")
        except ValueError:
            entry.configure(bg="#ffcccc")  # 非数字→红色

    def _get_invalid_fields(self):
        """收集所有非法输入字段"""
        invalid = []
        number_fields = [
            ("cost", "商品成本"), ("domestic", "发往义乌运费"),
            ("net_w", "裸重"), ("net_l", "裸长"), ("net_wi", "裸宽"), ("net_h", "裸高"),
            ("pkg_w", "包装后重量"), ("pkg_l", "包装后长"), ("pkg_wi", "包装后宽"), ("pkg_h", "包装后高"),
            ("tail", "尾程费用"), ("shein", "SHEIN二次核价"),
            ("price_rmb", "售价人民币"), ("price_usd", "售价美元"),
            ("target_rate", "目标净利率"), ("promo_rate", "推广预留比例"),
        ]
        for name, label in number_fields:
            if name in self._entry_vars:
                val = self._entry_vars[name].get().strip()
                if val != "" and not _is_valid_number(val):
                    invalid.append(f"{label}(非法输入)")
        # 检查利润率+推广≥100%
        tr = _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get() if "target_rate" in self._entry_vars else "")
        pr = _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get() if "promo_rate" in self._entry_vars else "")
        if tr is not None and pr is not None and (tr + pr) >= 100:
            invalid.append(f"目标净利率+推广预留≥100%（当前{tr+pr:.0f}%），无法定价")
        return invalid

    def _validate_all_on_save(self):
        """保存前校验，返回是否通过"""
        invalid = self._get_invalid_fields()
        if invalid:
            msg = "以下字段存在错误，请修正后再保存：\n\n" + "\n".join(f"  - {f}" for f in invalid)
            messagebox.showwarning("输入错误", msg)
            return False
        return True

    # ─── 事件处理 ─────────────────────────────────────────

    def _on_field_changed(self, field_type):
        if self._programmatic:
            return
        if field_type in ("price_rmb", "price_usd"):
            self._calc_direction = "price"
            self._last_modified = field_type
        elif field_type == "target_rate":
            self._calc_direction = "rate"
        if self._historical_mode:
            self._historical_mode = False
            self._show_rate_notice(None)
        self.recalculate()

    def recalculate(self):
        if self._historical_mode:
            return
        self._programmatic = True
        try:
            self._do_recalculate()
        finally:
            self._programmatic = False

    def _force_recalc(self):
        self._historical_mode = False
        self._show_rate_notice(None)
        # 重置尾程为当前默认值
        self._programmatic = True
        try:
            self._var_tail_haul.set(str(self._cfg.default_tail_haul))
        finally:
            self._programmatic = False
        self.recalculate()

    def _do_recalculate(self):
        # 读取输入
        cost = _safe_float(self._entry_vars.get("cost", tk.StringVar()).get())
        domestic = _safe_float(self._entry_vars.get("domestic", tk.StringVar()).get())
        pkg_w = _safe_float(self._entry_vars.get("pkg_w", tk.StringVar()).get())
        pkg_l = _safe_float(self._entry_vars.get("pkg_l", tk.StringVar()).get())
        pkg_wi = _safe_float(self._entry_vars.get("pkg_wi", tk.StringVar()).get())
        pkg_h = _safe_float(self._entry_vars.get("pkg_h", tk.StringVar()).get())
        tail_haul = _safe_float(self._entry_vars.get("tail", tk.StringVar()).get())
        price_rmb = _safe_float(self._entry_vars.get("price_rmb", tk.StringVar()).get())
        target_rate = _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get())
        promo_rate = _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get())
        exchange_rate = self._cfg.exchange_rate
        forwarder = self._get_forwarder_key()
        route = self._cfg.get_route_rates(forwarder) if forwarder else None

        # 未选货代
        if forwarder is None:
            self._set_result("head_haul", None, suffix=" (请选择货代)")
            self._set_result("total_logistics", None)
            self._set_result("total_cost", None)
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
            self._set_result("suggested_price", None)
            self._set_result("converted_usd", None)
            self._calculated = {}
            return

        head_rate = route["head_haul_rate"] if route else 0
        fixed_fee = route["fixed_service_fee"] if route else 0
        vol_div = self._cfg.volume_divisor

        # USD→RMB
        if self._last_modified == "price_usd":
            price_usd = _safe_float(self._entry_vars.get("price_usd", tk.StringVar()).get())
            if price_usd is not None and exchange_rate > 0:
                price_rmb = price_usd * exchange_rate
                self._entry_vars.get("price_rmb", tk.StringVar()).set(f"{price_rmb:.2f}")
                self._last_modified = "price_rmb"

        # 体积重
        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        self._set_result("vol_weight", vol_w, " kg")
        self._calculated["vol_weight"] = vol_w

        # 计费重量
        chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("charge_weight", chg_w, " kg")
        self._calculated["charge_weight"] = chg_w

        # 头程费用
        head_cost = head_haul_cost(chg_w, head_rate)
        head_partial = (head_cost is None)
        if head_cost is not None:
            self._set_result("head_haul", head_cost, f" 元({self._cfg.get_forwarder_label(forwarder)})")
        else:
            self._set_result("head_haul", None, partial=True)
        self._calculated["head_haul"] = head_cost
        self._partial["head_haul"] = head_partial

        # 总物流成本
        logistics = total_logistics_cost(head_cost, fixed_fee, tail_haul)
        log_partial = head_partial
        self._set_result("total_logistics", logistics, " 元", partial=log_partial)
        self._calculated["total_logistics"] = logistics
        self._partial["total_logistics"] = log_partial

        # 总成本
        tc = total_cost(cost, domestic, logistics)
        self._set_result("total_cost", tc, " 元", partial=log_partial)
        self._calculated["total_cost"] = tc
        self._partial["total_cost"] = log_partial

        # 利润
        if log_partial:
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
            self._set_result("suggested_price", None)
            self._set_result("converted_usd", None)
            return

        p_rate = promo_rate if promo_rate is not None else 0

        if self._calc_direction == "rate" and target_rate is not None and tc is not None:
            # 检查利润率+推广≥100%
            if (target_rate + p_rate) >= 100:
                self._set_result("suggested_price", None, suffix=" (利润率+推广≥100%)")
                self._set_result("profit", None, " 元")
                self._set_result("profit_rate", None, " %")
                return
            suggested = suggested_price_from_rate(tc, target_rate, promo_rate or 0)
            self._set_result("suggested_price", suggested, " 元")
            self._calculated["suggested_price"] = suggested
            if suggested is not None:
                usd_s = rmb_to_usd(suggested, exchange_rate)
                self._set_result("converted_usd", usd_s, " $")
            if price_rmb is not None and price_rmb > 0:
                np = net_profit_amount(price_rmb, tc, p_rate)
                self._set_result("profit", np, " 元")
                self._calculated["profit"] = np
                npr = net_profit_rate(price_rmb, tc, p_rate)
                self._set_result("profit_rate", npr, " %")
                self._calculated["profit_rate"] = npr
                usd = rmb_to_usd(price_rmb, exchange_rate)
                if usd is not None:
                    self._entry_vars.get("price_usd", tk.StringVar()).set(f"{usd:.2f}")
            else:
                self._set_result("profit", None, " 元")
                self._set_result("profit_rate", None, " %")
        else:
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
                    self._entry_vars.get("price_usd", tk.StringVar()).set(f"{usd:.2f}")
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
            if partial and suffix:
                var.set(f"数据不足{suffix}")
            elif partial:
                var.set("数据不足(物流费用不完整)")
            elif suffix:
                var.set(f"数据不足{suffix}")
            else:
                var.set("数据不足")
        elif partial:
            var.set(f"≥{value:.2f}{suffix}(估算)")
        else:
            var.set(f"{value:.2f}{suffix}")

    def _show_rate_notice(self, rules_diff):
        if rules_diff:
            lines = []
            if 'exchange_rate' in rules_diff:
                lines.append(f"汇率 {rules_diff['exchange_rate'][0]:.2f}→{rules_diff['exchange_rate'][1]:.2f}")
            if 'head_haul_rate' in rules_diff:
                lines.append(f"头程 {rules_diff['head_haul_rate'][0]:.0f}→{rules_diff['head_haul_rate'][1]:.0f}元/kg")
            if 'fixed_service_fee' in rules_diff:
                lines.append(f"固定费 {rules_diff['fixed_service_fee'][0]:.0f}→{rules_diff['fixed_service_fee'][1]:.0f}元")
            if 'forwarder' in rules_diff:
                lines.append(f"货代 {rules_diff['forwarder'][0]}→{rules_diff['forwarder'][1]}")
            self._rate_notice_var.set("历史记录 | 费率已变更: " + ", ".join(lines) + " | 点「用当前规则重算」更新")
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
        self._forwarder_var.set("")
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
            for name, var in self._entry_vars.items():
                if name in ("tail",):
                    var.set(str(self._cfg.default_tail_haul))
                else:
                    var.set("")
            self._forwarder_var.set("")
            self._var_name.set("")
            self._var_notes.set("")
            for key in self._result_labels:
                self._result_labels[key].set("—")
            self._calculated = {}
            self._partial = {}
        finally:
            self._programmatic = False

    def save_product(self):
        if not self._validate_all_on_save():
            return
        data = self._gather_data()
        if self._product_id:
            self._db.update_product(self._product_id, data)
            self._historical_mode = False
            self._show_rate_notice(None)
            messagebox.showinfo("提示", f"商品 {self._product_id} 已更新。")
        else:
            self._product_id = self._db.create_product(data)
            forwarder = self._get_forwarder_key()
            route = self._cfg.get_route_rates(forwarder) if forwarder else {}
            rules = {
                "exchange_rate": self._cfg.exchange_rate,
                "head_haul_rate": route.get("head_haul_rate"),
                "fixed_service_fee": route.get("fixed_service_fee"),
                "tail_haul_cost": _safe_float(self._entry_vars.get("tail", tk.StringVar()).get()) if "tail" in self._entry_vars else self._cfg.default_tail_haul,
                "volume_divisor": self._cfg.volume_divisor,
                "forwarder": forwarder,
                "rule_version": self._cfg.rule_version,
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
        full_rules = snap.get("_snapshot_rule_full", {})
        self._set_forwarder_key(full_rules.get("forwarder", "") if isinstance(full_rules, dict) else "")
        self._populate_results_from_snapshot(snap, full_rules)
        messagebox.showinfo("提示", "已还原到首次保存的状态。")

    def load_product(self, product_id: str):
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
        # 设置货代
        fwd = product.get("freight_forwarder")
        if fwd:
            self._set_forwarder_key(fwd)
        else:
            self._forwarder_var.set("")

        self._populate_results_from_product(product)
        self._check_rate_changes()

    def _populate_results_from_product(self, product):
        """从DB填充结果（历史模式）"""
        pkg_l = product.get("packaged_length")
        pkg_wi = product.get("packaged_width")
        pkg_h = product.get("packaged_height")
        pkg_w = product.get("packaged_weight")

        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        self._set_result("vol_weight", vol_w, " kg")
        chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("charge_weight", chg_w, " kg")

        head = product.get("head_haul_cost")
        if head is not None:
            fwd_label = self._cfg.get_forwarder_label(product.get("freight_forwarder", ""))
            self._set_result("head_haul", head, f" 元({fwd_label})" if fwd_label else " 元")
        else:
            self._set_result("head_haul", None, partial=True)

        fixed = product.get("fixed_service_fee") or 0
        tail = product.get("tail_haul_cost") or 0
        logistics = (head or 0) + fixed + tail if head is not None else None
        head_partial = (head is None)
        self._set_result("total_logistics", logistics, " 元", partial=head_partial)

        cost = product.get("cost") or 0
        domestic = product.get("domestic_shipping") or 0
        tc = (cost + domestic + (logistics or 0)) if logistics is not None else None
        self._set_result("total_cost", tc, " 元", partial=(head_partial or tc is None))

        price_rmb = product.get("selling_price_rmb")
        promo = product.get("promotion_reserve_rate") or 0
        if head_partial or tc is None:
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
        elif price_rmb is not None and price_rmb > 0:
            np = net_profit_amount(price_rmb, tc, promo)
            self._set_result("profit", np, " 元")
            npr = net_profit_rate(price_rmb, tc, promo)
            self._set_result("profit_rate", npr, " %")
        else:
            self._set_result("profit", None, " 元")
            self._set_result("profit_rate", None, " %")

        usd = product.get("selling_price_usd")
        self._set_result("converted_usd", usd, " $")
        self._set_result("suggested_price", None)
        self._calculated = {}
        self._partial = {}

    def _populate_results_from_snapshot(self, snap, full_rules):
        """从快照还原结果"""
        pkg_l = snap.get("packaged_length")
        pkg_wi = snap.get("packaged_width")
        pkg_h = snap.get("packaged_height")
        pkg_w = snap.get("packaged_weight")
        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        self._set_result("vol_weight", vol_w, " kg")
        chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("charge_weight", chg_w, " kg")
        head = snap.get("head_haul_cost")
        fwd = full_rules.get("forwarder", "") if isinstance(full_rules, dict) else ""
        fwd_label = self._cfg.get_forwarder_label(fwd)
        self._set_result("head_haul", head, f" 元({fwd_label})" if fwd_label and head else " 元")
        fixed = snap.get("fixed_service_fee") or 0
        tail = snap.get("tail_haul_cost") or 0
        logistics = (head or 0) + fixed + tail
        self._set_result("total_logistics", logistics, " 元")
        cost = snap.get("cost") or 0
        domestic = snap.get("domestic_shipping") or 0
        tc = cost + domestic + logistics
        self._set_result("total_cost", tc, " 元")
        price_rmb = snap.get("selling_price_rmb")
        promo = snap.get("promotion_reserve_rate") or 0
        if price_rmb is not None and price_rmb > 0:
            np = net_profit_amount(price_rmb, tc, promo)
            self._set_result("profit", np, " 元")
            npr = net_profit_rate(price_rmb, tc, promo)
            self._set_result("profit_rate", npr, " %")
        usd = snap.get("selling_price_usd")
        self._set_result("converted_usd", usd, " $")
        self._set_result("suggested_price", None)
        self._calculated = {}
        self._partial = {}

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

        full_rules = snap.get("_snapshot_rule_full", {})
        if isinstance(full_rules, dict):
            snap_head = full_rules.get("head_haul_rate")
            snap_fwd = full_rules.get("forwarder")
            current_fwd = self._get_forwarder_key()
            current_route = self._cfg.get_route_rates(current_fwd) if current_fwd else {}

            if snap_head is not None and current_route:
                cur_head = current_route.get("head_haul_rate")
                if cur_head is not None and abs(snap_head - cur_head) > 0.001:
                    changes["head_haul_rate"] = (snap_head, cur_head)
            snap_fixed = full_rules.get("fixed_service_fee")
            if snap_fixed is not None and current_route:
                cur_fixed = current_route.get("fixed_service_fee")
                if cur_fixed is not None and abs(snap_fixed - cur_fixed) > 0.001:
                    changes["fixed_service_fee"] = (snap_fixed, cur_fixed)

            if snap_fwd and snap_fwd != current_fwd:
                changes["forwarder"] = (self._cfg.get_forwarder_label(snap_fwd), self._cfg.get_forwarder_label(current_fwd or ""))
        else:
            # 旧快照无完整规则
            snap_head_v1 = snap.get("_snapshot_head_haul_rate")
            if snap_head_v1 is not None:
                current_route = self._cfg.get_route_rates(self._get_forwarder_key()) if self._get_forwarder_key() else {}
                cur_head = current_route.get("head_haul_rate", 100.0)
                if abs(snap_head_v1 - cur_head) > 0.001:
                    changes["head_haul_rate"] = (snap_head_v1, cur_head)

        if changes:
            self._show_rate_notice(changes)
        else:
            self._show_rate_notice(None)

    def _gather_data(self) -> dict:
        return {
            "name": self._var_name.get(),
            "cost": _safe_float(self._entry_vars.get("cost", tk.StringVar()).get()),
            "domestic_shipping": _safe_float(self._entry_vars.get("domestic", tk.StringVar()).get()),
            "net_weight": _safe_float(self._entry_vars.get("net_w", tk.StringVar()).get()),
            "net_length": _safe_float(self._entry_vars.get("net_l", tk.StringVar()).get()),
            "net_width": _safe_float(self._entry_vars.get("net_wi", tk.StringVar()).get()),
            "net_height": _safe_float(self._entry_vars.get("net_h", tk.StringVar()).get()),
            "packaged_weight": _safe_float(self._entry_vars.get("pkg_w", tk.StringVar()).get()),
            "packaged_length": _safe_float(self._entry_vars.get("pkg_l", tk.StringVar()).get()),
            "packaged_width": _safe_float(self._entry_vars.get("pkg_wi", tk.StringVar()).get()),
            "packaged_height": _safe_float(self._entry_vars.get("pkg_h", tk.StringVar()).get()),
            "freight_forwarder": self._get_forwarder_key(),
            "head_haul_cost": self._calculated.get("head_haul"),
            "fixed_service_fee": self._cfg.get_route_rates(self._get_forwarder_key()).get("fixed_service_fee") if self._get_forwarder_key() and self._cfg.get_route_rates(self._get_forwarder_key()) else None,
            "tail_haul_cost": _safe_float(self._entry_vars.get("tail", tk.StringVar()).get()),
            "shein_price": _safe_float(self._entry_vars.get("shein", tk.StringVar()).get()),
            "selling_price_rmb": _safe_float(self._entry_vars.get("price_rmb", tk.StringVar()).get()),
            "selling_price_usd": _safe_float(self._entry_vars.get("price_usd", tk.StringVar()).get()),
            "target_profit_rate": _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get()),
            "promotion_reserve_rate": _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get()),
            "notes": self._var_notes.get(),
        }

    def _load_data(self, data: dict):
        self._programmatic = True
        try:
            field_map = {
                "cost": "cost", "domestic": "domestic_shipping",
                "net_w": "net_weight", "net_l": "net_length", "net_wi": "net_width", "net_h": "net_height",
                "pkg_w": "packaged_weight", "pkg_l": "packaged_length", "pkg_wi": "packaged_width", "pkg_h": "packaged_height",
                "tail": "tail_haul_cost", "shein": "shein_price",
                "price_rmb": "selling_price_rmb", "price_usd": "selling_price_usd",
                "target_rate": "target_profit_rate", "promo_rate": "promotion_reserve_rate",
            }
            for entry_name, data_key in field_map.items():
                if entry_name in self._entry_vars:
                    val = data.get(data_key)
                    if entry_name == "tail" and val is None:
                        val = self._cfg.default_tail_haul
                    self._entry_vars[entry_name].set(self._fmt(val))
            self._var_name.set(data.get("name", "") or "")
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
