"""
新商品测算页面 — fix_04

修复清单：
- 历史保存不丢失头程：_calculated 在 load 时正确填充
- 缺失物流费用：head/fixed/tail 为 None 时不转 0，显示"数据不足"
- 非法输入停止计算：_has_invalid 标志阻止计算
- 历史规则持久：saved_rule_context 独立于当前规则
- 完整规则变化检测：7 项比较
- UI文字：发往中转仓运费
"""

import math, tkinter as tk, sys, os
from tkinter import ttk, messagebox
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
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _is_valid_number(val):
    s = str(val).strip() if val is not None else ""
    if s == "":
        return True
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return False
        return f >= 0
    except (ValueError, TypeError):
        return False


def _is_valid_rate(val):
    """0 <= rate < 100"""
    s = str(val).strip() if val is not None else ""
    if s == "":
        return True
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return False
        return 0 <= f < 100
    except (ValueError, TypeError):
        return False


class ProductPage(ttk.Frame):
    def __init__(self, parent, db_manager, config_manager):
        super().__init__(parent)
        self._db = db_manager
        self._cfg = config_manager

        # 状态
        self._product_id = None
        self._calc_direction = None
        self._last_modified = None
        self._programmatic = False
        self._has_snapshot = False

        # saved_rule_context: 打开历史商品时保存的规则（不变）
        # current_rule_context: 当前 UI 选择的规则
        self._saved_rule_context = None   # dict 或 None
        self._current_fwd_key = None      # 当前货代 key
        self._show_rate_banner = False    # 是否显示费率变更提示

        # 计算缓存（保存时使用，不受界面显示影响）
        self._computed = {}

        self._entry_vars = {}
        self._entry_widgets = {}
        self._build_ui()
        self.new_product()

    # ─── UI ───────────────────────────────────────────────

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
        self._rate_notice_label = ttk.Label(right, textvariable=self._rate_notice_var,
                                             foreground="#cc6600", font=("", 9, "italic"), wraplength=280)
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
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        var = tk.StringVar(value=default)
        entry = tk.Entry(parent, textvariable=var, width=22, bg="white", relief="sunken")
        entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=2)
        var.trace_add("write", lambda *_, n=name: self._validate_field(n))
        self._entry_vars[name] = var
        self._entry_widgets[name] = entry
        return var

    def _make_section(self, parent, title, row_start):
        ttk.Label(parent, text=title, font=("", 10, "bold")).grid(row=row_start, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10, 2))

    def _build_inputs(self):
        pf = self._input_frame; r = 0

        self._make_section(pf, "基本信息", r); r += 1
        self._var_name = tk.StringVar()
        ttk.Entry(pf, textvariable=self._var_name, width=46).grid(row=r, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=2); r += 1
        self._var_cost = self._make_number_entry(pf, "商品成本 (元)：", r, "cost"); r += 1
        self._var_domestic = self._make_number_entry(pf, "发往中转仓运费 (元)：", r, "domestic"); r += 1

        # 货代
        self._make_section(pf, "货代选择", r); r += 1
        ff = ttk.Frame(pf); ff.grid(row=r, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        ttk.Label(ff, text="货代：").pack(side=tk.LEFT)
        self._forwarder_var = tk.StringVar(value="")
        cb = ttk.Combobox(ff, textvariable=self._forwarder_var, values=["", "深圳", "义乌"], state="readonly", width=10)
        cb.pack(side=tk.LEFT, padx=5)
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_forwarder_changed())
        ttk.Label(ff, text="(留空=未选择)", foreground="gray", font=("", 8)).pack(side=tk.LEFT, padx=5); r += 1

        self._make_section(pf, "裸件数据", r); r += 1
        self._var_net_w = self._make_number_entry(pf, "裸重 (kg)：", r, "net_w"); r += 1
        self._var_net_l = self._make_number_entry(pf, "裸长 (cm)：", r, "net_l"); r += 1
        self._var_net_wi = self._make_number_entry(pf, "裸宽 (cm)：", r, "net_wi"); r += 1
        self._var_net_h = self._make_number_entry(pf, "裸高 (cm)：", r, "net_h"); r += 1

        self._make_section(pf, "包装数据", r); r += 1
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

        # trace
        for n in ["cost","domestic","net_w","net_l","net_wi","net_h","pkg_w","pkg_l","pkg_wi","pkg_h","tail","shein"]:
            if n in self._entry_vars:
                self._entry_vars[n].trace_add("write", lambda *_, x=n: self._on_field_changed("cost"))
        for n in ["price_rmb","price_usd","target_rate","promo_rate"]:
            if n in self._entry_vars:
                self._entry_vars[n].trace_add("write", lambda *_, x=n: self._on_field_changed(x))

    def _build_results(self, parent):
        ttk.Label(parent, text="计算结果", font=("", 11, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 10))
        self._result_labels = {}
        for key, label in [
            ("vol_weight","体积重 (kg)："), ("charge_weight","计费重量 (kg)："),
            ("head_haul","头程费用 (元)："), ("total_logistics","总物流成本 (元)："),
            ("total_cost","总成本 (元)："), ("profit","净利润 (元)："),
            ("profit_rate","净利率 (%)："), ("suggested_price","建议售价 (元)："),
            ("converted_usd","折合美元 ($)："),
        ]:
            frm = ttk.Frame(parent); frm.pack(fill=tk.X, padx=5, pady=2)
            ttk.Label(frm, text=label, width=18).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            ttk.Label(frm, textvariable=var, font=("", 10, "bold")).pack(side=tk.LEFT)
            self._result_labels[key] = var

    # ─── 校验 ─────────────────────────────────────────────

    def _validate_field(self, name):
        entry = self._entry_widgets.get(name)
        var = self._entry_vars.get(name)
        if not entry or not var: return
        val = var.get().strip()
        if val == "":
            entry.configure(bg="white"); return
        if name in ("target_rate", "promo_rate"):
            ok = _is_valid_rate(val)
        else:
            ok = _is_valid_number(val)
        entry.configure(bg="white" if ok else "#ffcccc")

    def _has_any_invalid(self):
        """检查是否有非法输入"""
        for name in self._entry_vars:
            val = self._entry_vars[name].get().strip()
            if val == "": continue
            if name in ("target_rate", "promo_rate"):
                if not _is_valid_rate(val): return True
            else:
                if not _is_valid_number(val): return True
        tr = _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get())
        pr = _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get())
        if tr is not None and pr is not None and (tr + pr) >= 100:
            return True
        return False

    def _get_invalid_list(self):
        inv = []
        for name, label in [
            ("cost","商品成本"),("domestic","发往中转仓运费"),
            ("net_w","裸重"),("net_l","裸长"),("net_wi","裸宽"),("net_h","裸高"),
            ("pkg_w","包装后重量"),("pkg_l","包装后长"),("pkg_wi","包装后宽"),("pkg_h","包装后高"),
            ("tail","尾程费用"),("shein","SHEIN二次核价"),
            ("price_rmb","售价人民币"),("price_usd","售价美元"),
        ]:
            if name in self._entry_vars:
                v = self._entry_vars[name].get().strip()
                if v != "" and not _is_valid_number(v):
                    inv.append(f"{label}(非法)")
        for name, label in [("target_rate","目标净利率"),("promo_rate","推广预留比例")]:
            if name in self._entry_vars:
                v = self._entry_vars[name].get().strip()
                if v != "" and not _is_valid_rate(v):
                    inv.append(f"{label}(非法)")
        tr = _safe_float(self._entry_vars.get("target_rate", tk.StringVar()).get())
        pr = _safe_float(self._entry_vars.get("promo_rate", tk.StringVar()).get())
        if tr is not None and pr is not None and (tr + pr) >= 100:
            inv.append(f"目标净利率+推广预留≥100%（{tr+pr:.0f}%）")
        return inv

    # ─── 事件 ─────────────────────────────────────────────

    def _on_field_changed(self, field_type):
        if self._programmatic: return
        if field_type in ("price_rmb","price_usd"):
            self._calc_direction = "price"; self._last_modified = field_type
        elif field_type == "target_rate":
            self._calc_direction = "rate"
        # 如果当前在历史模式且有保存的规则上下文，编辑成本/备注等字段不应退出历史规则
        # 只有货代变更或点击重算才退出
        self.recalculate()

    def _on_forwarder_changed(self):
        if self._programmatic: return
        self._saved_rule_context = None  # 用户改了货代 → 放弃历史规则
        self._show_rate_banner = False
        self._show_rate_notice(None)
        self.recalculate()

    def recalculate(self):
        if self._programmatic: return
        self._programmatic = True
        try:
            if self._has_any_invalid():
                # 清空所有结果
                for key in self._result_labels:
                    self._result_labels[key].set("输入错误")
                self._computed = {}
            else:
                self._do_recalculate()
        finally:
            self._programmatic = False

    def _force_recalc(self):
        """用当前规则重算：放弃保存的规则上下文"""
        self._saved_rule_context = None
        self._show_rate_banner = False
        self._show_rate_notice(None)
        self._programmatic = True
        try:
            self._entry_vars["tail"].set(str(self._cfg.default_tail_haul))
        finally:
            self._programmatic = False
        self.recalculate()

    def _get_active_rule_context(self):
        """获取当前生效的规则上下文（优先历史保存的，否则用当前配置）"""
        if self._saved_rule_context is not None:
            return self._saved_rule_context
        # 使用当前 UI 选择的货代
        fwd_key = self._get_forwarder_key()
        route = self._cfg.get_route_rates(fwd_key) if fwd_key else None
        return {
            "forwarder": fwd_key,
            "head_haul_rate": route["head_haul_rate"] if route else None,
            "fixed_service_fee": route["fixed_service_fee"] if route else None,
            "exchange_rate": self._cfg.exchange_rate,
            "volume_divisor": VOLUME_DIVISOR,
        }

    def _get_forwarder_key(self):
        label = self._forwarder_var.get()
        if label == "深圳": return "shenzhen"
        if label == "义乌": return "yiwu"
        return None

    def _set_forwarder_key(self, key):
        self._forwarder_var.set(FORWARDER_LABELS.get(key, ""))

    def _do_recalculate(self):
        ctx = self._get_active_rule_context()

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

        head_rate = ctx.get("head_haul_rate")
        fixed_fee = ctx.get("fixed_service_fee")
        exchange_rate = ctx.get("exchange_rate", 7.20)
        vol_div = ctx.get("volume_divisor", VOLUME_DIVISOR)
        forwarder = ctx.get("forwarder")

        # 未选货代 or 费率缺失 → 不计算利润
        if forwarder is None or head_rate is None or fixed_fee is None:
            self._set_result("head_haul", None, suffix=" (请选择货代)")
            self._set_result("total_logistics", None)
            self._set_result("total_cost", None)
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
            self._set_result("suggested_price", None)
            self._set_result("converted_usd", None)
            self._computed = {"head_haul": None, "total_logistics": None, "total_cost": None,
                              "profit": None, "profit_rate": None, "suggested_price": None}
            return

        # USD→RMB
        if self._last_modified == "price_usd":
            pu = _safe_float(self._entry_vars.get("price_usd", tk.StringVar()).get())
            if pu is not None and exchange_rate > 0:
                price_rmb = pu * exchange_rate
                self._entry_vars.get("price_rmb", tk.StringVar()).set(f"{price_rmb:.2f}")
                self._last_modified = "price_rmb"

        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        chg_w = chargeable_weight(pkg_w, vol_w)
        head_cost = head_haul_cost(chg_w, head_rate)

        # 缺失传播：head 为 None 则 logistics/total_cost/profit 全部不可靠
        head_partial = (head_cost is None)

        self._set_result("vol_weight", vol_w, " kg")
        self._set_result("charge_weight", chg_w, " kg")

        fwd_label = FORWARDER_LABELS.get(forwarder, forwarder or "")
        if head_cost is not None:
            self._set_result("head_haul", head_cost, f" 元({fwd_label})")
        else:
            self._set_result("head_haul", None, partial=True)

        self._computed["head_haul"] = head_cost
        self._computed["fixed_service_fee"] = fixed_fee
        self._computed["tail_haul_cost"] = tail_haul
        self._computed["exchange_rate"] = exchange_rate
        self._computed["forwarder"] = forwarder

        # 总物流：头程缺失 → 仅显示已知部分 + 标记估算
        logistics = None
        if not head_partial:
            logistics = total_logistics_cost(head_cost, fixed_fee, tail_haul)
        elif fixed_fee is not None or tail_haul is not None:
            logistics = total_logistics_cost(None, fixed_fee, tail_haul)
        self._set_result("total_logistics", logistics, " 元", partial=head_partial)
        self._computed["total_logistics"] = logistics

        # 总成本
        tc = None
        if not head_partial:
            tc = total_cost(cost, domestic, logistics)
        self._set_result("total_cost", tc, " 元", partial=head_partial)
        self._computed["total_cost"] = tc

        if head_partial:
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
            self._set_result("suggested_price", None)
            self._set_result("converted_usd", None)
            self._computed["profit"] = None
            self._computed["profit_rate"] = None
            self._computed["suggested_price"] = None
            return

        p_rate = promo_rate if promo_rate is not None else 0

        if self._calc_direction == "rate" and target_rate is not None and tc is not None:
            if (target_rate + p_rate) >= 100:
                self._set_result("suggested_price", None, suffix=" (利润率+推广≥100%)")
                self._set_result("profit", None, " 元")
                self._set_result("profit_rate", None, " %")
                return
            sp = suggested_price_from_rate(tc, target_rate, promo_rate or 0)
            self._set_result("suggested_price", sp, " 元")
            self._computed["suggested_price"] = sp
            if sp is not None:
                self._set_result("converted_usd", rmb_to_usd(sp, exchange_rate), " $")
            if price_rmb is not None and price_rmb > 0:
                np = net_profit_amount(price_rmb, tc, p_rate); npr = net_profit_rate(price_rmb, tc, p_rate)
                self._set_result("profit", np, " 元"); self._set_result("profit_rate", npr, " %")
                self._computed["profit"] = np; self._computed["profit_rate"] = npr
                u = rmb_to_usd(price_rmb, exchange_rate)
                if u is not None: self._entry_vars["price_usd"].set(f"{u:.2f}")
            else:
                self._set_result("profit", None, " 元"); self._set_result("profit_rate", None, " %")
                self._computed["profit"] = None; self._computed["profit_rate"] = None
        else:
            if price_rmb is not None and price_rmb > 0:
                np = net_profit_amount(price_rmb, tc, p_rate); npr = net_profit_rate(price_rmb, tc, p_rate)
                self._set_result("profit", np, " 元"); self._set_result("profit_rate", npr, " %")
                self._computed["profit"] = np; self._computed["profit_rate"] = npr
                u = rmb_to_usd(price_rmb, exchange_rate)
                self._set_result("converted_usd", u, " $")
                if u is not None: self._entry_vars["price_usd"].set(f"{u:.2f}")
            else:
                self._set_result("profit", None, " 元"); self._set_result("profit_rate", None, " %")
                self._set_result("converted_usd", None, " $")
                self._computed["profit"] = None; self._computed["profit_rate"] = None
            self._set_result("suggested_price", None)
            self._computed["suggested_price"] = None

    def _set_result(self, key, value, suffix="", partial=False):
        var = self._result_labels.get(key)
        if not var: return
        if value is None:
            if partial and suffix: var.set(f"数据不足{suffix}")
            elif partial: var.set("数据不足(物流费用不完整)")
            elif suffix: var.set(f"数据不足{suffix}")
            else: var.set("数据不足")
        elif partial:
            var.set(f"≥{value:.2f}{suffix}(估算)")
        else:
            var.set(f"{value:.2f}{suffix}")

    def _show_rate_notice(self, diffs):
        if diffs:
            lines = []
            for k, (old, new) in diffs.items():
                labels = {"exchange_rate":"汇率","head_haul_rate":"头程单价","fixed_service_fee":"固定服务费",
                          "tail_haul_cost":"尾程费用","volume_divisor":"体积除数","forwarder":"货代","rule_version":"规则版本"}
                lbl = labels.get(k, k)
                if isinstance(old, float) and isinstance(new, float):
                    lines.append(f"{lbl} {old:.2f}→{new:.2f}")
                else:
                    old_s = str(old) if old else "未知"; new_s = str(new) if new else "未知"
                    lines.append(f"{lbl} {old_s}→{new_s}")
            self._rate_notice_var.set("历史记录 | 费率已变更: " + ", ".join(lines) + " | 点「用当前规则重算」更新")
            if not self._rate_notice_label.winfo_ismapped():
                children = self._results_frame.winfo_children()
                target = children[0] if children else None
                if target:
                    self._rate_notice_label.pack(in_=self._results_frame, before=target, fill=tk.X, padx=5, pady=(0, 5))
                else:
                    self._rate_notice_label.pack(in_=self._results_frame, fill=tk.X, padx=5, pady=(0, 5))
        else:
            self._rate_notice_var.set("")
            self._rate_notice_label.pack_forget()

    # ─── 按钮 ─────────────────────────────────────────────

    def new_product(self):
        self._product_id = None; self._has_snapshot = False
        self._calc_direction = None; self._last_modified = None
        self._saved_rule_context = None; self._show_rate_banner = False
        self._show_rate_notice(None)
        self._forwarder_var.set("")
        self.clear_form()

    def clear_form(self):
        self._product_id = None; self._has_snapshot = False
        self._saved_rule_context = None; self._show_rate_banner = False
        self._calc_direction = None; self._last_modified = None
        self._show_rate_notice(None)
        self._programmatic = True
        try:
            for n, v in self._entry_vars.items():
                v.set(str(self._cfg.default_tail_haul) if n == "tail" else "")
            self._var_name.set(""); self._var_notes.set("")
            self._forwarder_var.set("")
            for k in self._result_labels: self._result_labels[k].set("—")
            self._computed = {}
        finally:
            self._programmatic = False

    def save_product(self):
        inv = self._get_invalid_list()
        if inv:
            messagebox.showwarning("输入错误", "以下字段存在错误：\n\n" + "\n".join(f"  - {f}" for f in inv))
            return

        data = self._gather_data()
        if self._product_id:
            self._db.update_product(self._product_id, data)
            self._saved_rule_context = None; self._show_rate_banner = False
            self._show_rate_notice(None)
            messagebox.showinfo("提示", f"商品 {self._product_id} 已更新。")
        else:
            self._product_id = self._db.create_product(data)
            rules = {
                "exchange_rate": self._computed.get("exchange_rate", self._cfg.exchange_rate),
                "head_haul_rate": self._computed.get("head_haul_rate"),
                "fixed_service_fee": self._computed.get("fixed_service_fee"),
                "tail_haul_cost": self._computed.get("tail_haul_cost"),
                "volume_divisor": VOLUME_DIVISOR,
                "forwarder": self._computed.get("forwarder"),
                "rule_version": self._cfg.rule_version,
            }
            self._db.save_snapshot(self._product_id, data, rules)
            self._has_snapshot = True
            messagebox.showinfo("提示", f"商品已保存，ID: {self._product_id}")

    def restore_product(self):
        if not self._product_id:
            messagebox.showinfo("提示", "尚未保存，无法还原。"); return
        snap = self._db.get_snapshot(self._product_id)
        if not snap:
            messagebox.showinfo("提示", "没有可还原的快照。"); return
        self._load_data(snap)
        full = snap.get("_snapshot_rule_full", {})
        if isinstance(full, dict):
            self._set_forwarder_key(full.get("forwarder", ""))
        self._saved_rule_context = None
        self._populate_results_from_saved(snap)
        messagebox.showinfo("提示", "已还原到首次保存的状态。")

    def load_product(self, product_id: str):
        product = self._db.get_product(product_id)
        if not product:
            messagebox.showerror("错误", f"未找到: {product_id}"); return
        self._product_id = product_id
        self._has_snapshot = self._db.get_snapshot(product_id) is not None
        self._calc_direction = None; self._last_modified = None

        self._load_data(product)
        fwd = product.get("freight_forwarder")
        self._set_forwarder_key(fwd if fwd else "")

        # 重建 saved_rule_context：从数据库恢复当时的规则
        snap = self._db.get_snapshot(product_id)
        if snap:
            full = snap.get("_snapshot_rule_full", {})
            if isinstance(full, dict) and full:
                self._saved_rule_context = {
                    "forwarder": fwd,
                    "head_haul_rate": full.get("head_haul_rate"),
                    "fixed_service_fee": full.get("fixed_service_fee"),
                    "exchange_rate": snap.get("_snapshot_exchange_rate", self._cfg.exchange_rate),
                    "volume_divisor": snap.get("_snapshot_volume_divisor", VOLUME_DIVISOR),
                }
            elif snap.get("_snapshot_head_haul_rate") is not None:
                # 旧快照（v1格式，无 full rules）
                self._saved_rule_context = {
                    "forwarder": fwd,
                    "head_haul_rate": snap["_snapshot_head_haul_rate"],
                    "fixed_service_fee": snap.get("_snapshot_fixed_service_fee"),
                    "exchange_rate": snap.get("_snapshot_exchange_rate", self._cfg.exchange_rate),
                    "volume_divisor": snap.get("_snapshot_volume_divisor", VOLUME_DIVISOR),
                }
            else:
                self._saved_rule_context = None
        else:
            self._saved_rule_context = None

        self._show_rate_banner = True
        self._populate_results_from_saved(product)
        if self._saved_rule_context:
            self._check_rate_changes()

    def _populate_results_from_saved(self, data):
        """从数据库记录填充结果（不依赖当前规则）"""
        pkg_l = data.get("packaged_length"); pkg_wi = data.get("packaged_width")
        pkg_h = data.get("packaged_height"); pkg_w = data.get("packaged_weight")
        vol_w = volumetric_weight(pkg_l, pkg_wi, pkg_h)
        chg_w = chargeable_weight(pkg_w, vol_w)
        self._set_result("vol_weight", vol_w, " kg")
        self._set_result("charge_weight", chg_w, " kg")

        head = data.get("head_haul_cost")
        fwd = data.get("freight_forwarder") or ""
        if head is not None:
            self._set_result("head_haul", head, f" 元({FORWARDER_LABELS.get(fwd, fwd)})" if fwd else " 元")
        else:
            self._set_result("head_haul", None, partial=True)

        # 检查关键费用缺失
        fixed = data.get("fixed_service_fee")
        tail = data.get("tail_haul_cost")
        missing_critical = (head is None or fixed is None or tail is None)

        logistics = (head + fixed + tail) if not missing_critical else None
        self._set_result("total_logistics", logistics, " 元", partial=missing_critical)

        cost = data.get("cost") or 0
        domestic = data.get("domestic_shipping") or 0
        tc = (cost + domestic + logistics) if logistics is not None else None
        self._set_result("total_cost", tc, " 元", partial=(missing_critical or tc is None))

        price_rmb = data.get("selling_price_rmb")
        promo = data.get("promotion_reserve_rate") or 0
        if missing_critical or tc is None:
            self._set_result("profit", None, partial=True)
            self._set_result("profit_rate", None, partial=True)
        elif price_rmb is not None and price_rmb > 0:
            np = net_profit_amount(price_rmb, tc, promo)
            npr = net_profit_rate(price_rmb, tc, promo)
            self._set_result("profit", np, " 元"); self._set_result("profit_rate", npr, " %")
            self._computed["profit"] = np; self._computed["profit_rate"] = npr
        else:
            self._set_result("profit", None, " 元"); self._set_result("profit_rate", None, " %")

        usd = data.get("selling_price_usd")
        self._set_result("converted_usd", usd, " $")
        self._set_result("suggested_price", None)

        # 填充 _computed 供保存使用
        self._computed = {
            "head_haul": head, "head_haul_rate": self._saved_rule_context["head_haul_rate"] if self._saved_rule_context else None,
            "fixed_service_fee": fixed, "tail_haul_cost": tail,
            "total_logistics": logistics, "total_cost": tc,
            "exchange_rate": self._saved_rule_context["exchange_rate"] if self._saved_rule_context else self._cfg.exchange_rate,
            "forwarder": fwd or None,
            "profit": self._computed.get("profit"), "profit_rate": self._computed.get("profit_rate"),
            "suggested_price": None,
        }

    def _check_rate_changes(self):
        if not self._saved_rule_context: return
        current = self._get_active_rule_context()
        saved = self._saved_rule_context
        diffs = {}
        for key in ["exchange_rate", "head_haul_rate", "fixed_service_fee", "volume_divisor", "forwarder"]:
            sv = saved.get(key); cv = current.get(key)
            if sv is not None and cv is not None:
                if isinstance(sv, float) and isinstance(cv, float):
                    if abs(sv - cv) > 0.001: diffs[key] = (sv, cv)
                elif sv != cv:
                    diffs[key] = (sv, cv)
        if diffs:
            self._show_rate_notice(diffs)
        else:
            self._show_rate_notice(None)

    def _gather_data(self):
        """从 _computed 字典收集保存数据（不依赖界面显示）"""
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
            "freight_forwarder": self._computed.get("forwarder"),
            "head_haul_cost": self._computed.get("head_haul"),
            "fixed_service_fee": self._computed.get("fixed_service_fee"),
            "tail_haul_cost": self._computed.get("tail_haul_cost"),
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
            fm = {"cost":"cost","domestic":"domestic_shipping",
                  "net_w":"net_weight","net_l":"net_length","net_wi":"net_width","net_h":"net_height",
                  "pkg_w":"packaged_weight","pkg_l":"packaged_length","pkg_wi":"packaged_width","pkg_h":"packaged_height",
                  "tail":"tail_haul_cost","shein":"shein_price",
                  "price_rmb":"selling_price_rmb","price_usd":"selling_price_usd",
                  "target_rate":"target_profit_rate","promo_rate":"promotion_reserve_rate"}
            for en, dk in fm.items():
                if en in self._entry_vars:
                    v = data.get(dk)
                    if en == "tail" and v is None: v = self._cfg.default_tail_haul
                    self._entry_vars[en].set(self._fmt(v))
            self._var_name.set(data.get("name","") or "")
            self._var_notes.set(data.get("notes","") or "")
        finally:
            self._programmatic = False

    @staticmethod
    def _fmt(val, default=""):
        if val is None: return str(default) if default else ""
        try: return f"{float(val):.2f}"
        except: return str(val)

    @property
    def product_id(self):
        return self._product_id
