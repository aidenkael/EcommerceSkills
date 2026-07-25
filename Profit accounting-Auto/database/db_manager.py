"""
SQLite 数据库管理 — Schema v2 (fix_05 原子迁移)

迁移规则：
- 新数据库：直接创建完整v2 schema，不备份不迁移
- 旧数据库：先只读检查→关闭→备份→事务迁移→提交/回滚
- 备份名: backup_v{old}_to_v2_{timestamp}.db
"""

import sqlite3, json, uuid, os, shutil
from datetime import datetime

CURRENT_SCHEMA_VERSION = 2
CURRENT_RULE_VERSION = 2
VOLUME_DIVISOR = 8000

DEFAULT_ROUTES = {
    "shenzhen": {"head_haul_rate": 80.0, "fixed_service_fee": 10.0, "description": "深圳货代"},
    "yiwu":     {"head_haul_rate": 100.0, "fixed_service_fee": 6.0, "description": "义乌货代"},
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS business_rule_version (version INTEGER PRIMARY KEY, description TEXT DEFAULT '', applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY, name TEXT DEFAULT '', cost REAL, domestic_shipping REAL,
    net_weight REAL, net_length REAL, net_width REAL, net_height REAL,
    packaged_weight REAL, packaged_length REAL, packaged_width REAL, packaged_height REAL,
    freight_forwarder TEXT DEFAULT NULL,
    head_haul_cost REAL, fixed_service_fee REAL, tail_haul_cost REAL,
    shein_price REAL, selling_price_rmb REAL, selling_price_usd REAL,
    target_profit_rate REAL, promotion_reserve_rate REAL,
    notes TEXT DEFAULT '', status TEXT DEFAULT 'active', image_path TEXT DEFAULT '',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS product_snapshots (
    id TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE,
    snapshot_data TEXT NOT NULL,
    exchange_rate REAL, head_haul_rate REAL, fixed_service_fee REAL,
    tail_haul_cost REAL, volume_divisor INTEGER DEFAULT 8000,
    rule_version INTEGER DEFAULT 1, rule_snapshot TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS route_config (
    forwarder TEXT PRIMARY KEY, head_haul_rate REAL NOT NULL,
    fixed_service_fee REAL NOT NULL, description TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

NUMERIC_FIELDS = [
    "cost", "domestic_shipping",
    "net_weight", "net_length", "net_width", "net_height",
    "packaged_weight", "packaged_length", "packaged_width", "packaged_height",
    "head_haul_cost", "fixed_service_fee", "tail_haul_cost",
    "shein_price", "selling_price_rmb", "selling_price_usd",
    "target_profit_rate", "promotion_reserve_rate",
]
DEFAULT_CONFIG = {"exchange_rate": "7.20", "default_tail_haul": "40.0"}


class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "profit_accounting.db")
        self.db_path = db_path
        db_exists = os.path.exists(self.db_path)

        if db_exists:
            old_version = self._peek_schema_version()
            if old_version < CURRENT_SCHEMA_VERSION:
                self._migrate_from(old_version)
            else:
                self._init_db()  # 已是v2，仅确保表存在
        else:
            # 新数据库：直接创建v2
            self._init_db()
            self._seed_v2_data()

    def _peek_schema_version(self) -> int:
        """只读连接读取版本号，读完后立即关闭"""
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
            return row["version"] if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _migrate_from(self, old_version: int):
        """从旧版本迁移到 v2"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.db_path + f".backup_v{old_version}_to_v2_{ts}.db"
        shutil.copy2(self.db_path, backup_path)

        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN TRANSACTION")
            # 确保所有v2表存在（逐条执行，不用executescript以免自动提交）
            for stmt in [
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS business_rule_version (version INTEGER PRIMARY KEY, description TEXT DEFAULT '', applied_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS route_config (forwarder TEXT PRIMARY KEY, head_haul_rate REAL NOT NULL, fixed_service_fee REAL NOT NULL, description TEXT DEFAULT '')",
                "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                # 确保核心表存在（v0可能缺失某些表）
                "CREATE TABLE IF NOT EXISTS product_snapshots (id TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE, snapshot_data TEXT NOT NULL, exchange_rate REAL, head_haul_rate REAL, fixed_service_fee REAL, tail_haul_cost REAL, volume_divisor INTEGER DEFAULT 8000, rule_version INTEGER DEFAULT 1, rule_snapshot TEXT, created_at TEXT NOT NULL, FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE)",
            ]:
                conn.execute(stmt)
            # 补列
            self._add_column_if_missing(conn, "products", "freight_forwarder", "TEXT DEFAULT NULL")
            self._add_column_if_missing(conn, "product_snapshots", "tail_haul_cost", "REAL")
            self._add_column_if_missing(conn, "product_snapshots", "volume_divisor", "INTEGER DEFAULT 8000")
            self._add_column_if_missing(conn, "product_snapshots", "rule_snapshot", "TEXT")
            # 种子数据
            for fwd, rates in DEFAULT_ROUTES.items():
                conn.execute("INSERT OR IGNORE INTO route_config VALUES (?,?,?,?)",
                             (fwd, rates["head_haul_rate"], rates["fixed_service_fee"], rates["description"]))
            br = conn.execute("SELECT version FROM business_rule_version LIMIT 1").fetchone()
            if br is None:
                conn.execute("INSERT INTO business_rule_version (version, description, applied_at) VALUES (?,?,?)",
                             (CURRENT_RULE_VERSION, "双货代规则", datetime.now().isoformat()))
            for k, v in DEFAULT_CONFIG.items():
                conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (k, v))
            # 最后写入版本号
            conn.execute("INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?,?)",
                         (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()))
            conn.execute("COMMIT")
        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass  # 可能事务尚未开始
            conn.close()
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, self.db_path)
            raise
        finally:
            if conn:
                conn.close()

    def _init_db(self):
        """建表（不写版本号，不写种子数据）"""
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def _seed_v2_data(self):
        """仅新数据库：写入版本号、配置、货代"""
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try:
            conn.execute("INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?,?)",
                         (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()))
            conn.execute("INSERT OR IGNORE INTO business_rule_version (version, description, applied_at) VALUES (?,?,?)",
                         (CURRENT_RULE_VERSION, "双货代规则", datetime.now().isoformat()))
            for k, v in DEFAULT_CONFIG.items():
                conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (k, v))
            for fwd, rates in DEFAULT_ROUTES.items():
                conn.execute("INSERT OR IGNORE INTO route_config VALUES (?,?,?,?)",
                             (fwd, rates["head_haul_rate"], rates["fixed_service_fee"], rates["description"]))
            conn.commit()
        finally:
            conn.close()

    def _add_column_if_missing(self, conn, table, column, col_type):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON"); return conn

    def get_schema_version(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
            return row["version"] if row else 0
        except sqlite3.OperationalError: return 0
        finally: conn.close()

    def get_rule_version(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT version FROM business_rule_version ORDER BY version DESC LIMIT 1").fetchone()
            return row["version"] if row else CURRENT_RULE_VERSION
        except sqlite3.OperationalError: return CURRENT_RULE_VERSION
        finally: conn.close()

    def get_route_rates(self, fwd: str) -> dict | None:
        conn = self._get_conn()
        try:
            r = conn.execute("SELECT head_haul_rate, fixed_service_fee FROM route_config WHERE forwarder = ?", (fwd,)).fetchone()
            return {"head_haul_rate": r["head_haul_rate"], "fixed_service_fee": r["fixed_service_fee"]} if r else None
        finally: conn.close()

    def get_all_routes(self) -> list[dict]:
        conn = self._get_conn()
        try: return [dict(r) for r in conn.execute("SELECT * FROM route_config").fetchall()]
        finally: conn.close()

    # ─── CRUD ────────────────────────────────────────────

    def create_product(self, data: dict) -> str:
        pid = str(uuid.uuid4())[:8]; now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            conn.execute("""INSERT INTO products (id,name,cost,domestic_shipping,
                net_weight,net_length,net_width,net_height,
                packaged_weight,packaged_length,packaged_width,packaged_height,
                freight_forwarder,head_haul_cost,fixed_service_fee,tail_haul_cost,
                shein_price,selling_price_rmb,selling_price_usd,
                target_profit_rate,promotion_reserve_rate,
                notes,status,image_path,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, data.get("name",""), data.get("cost"), data.get("domestic_shipping"),
                 data.get("net_weight"), data.get("net_length"), data.get("net_width"), data.get("net_height"),
                 data.get("packaged_weight"), data.get("packaged_length"), data.get("packaged_width"), data.get("packaged_height"),
                 data.get("freight_forwarder"), data.get("head_haul_cost"), data.get("fixed_service_fee"), data.get("tail_haul_cost"),
                 data.get("shein_price"), data.get("selling_price_rmb"), data.get("selling_price_usd"),
                 data.get("target_profit_rate"), data.get("promotion_reserve_rate"),
                 data.get("notes",""), data.get("status","active"), data.get("image_path",""), now, now))
            conn.commit(); return pid
        finally: conn.close()

    def update_product(self, pid: str, data: dict):
        now = datetime.now().isoformat(); data["updated_at"] = now
        sc = []; vs = []
        for f in NUMERIC_FIELDS + ["name","freight_forwarder","notes","status","image_path","updated_at"]:
            if f in data: sc.append(f"{f}=?"); vs.append(data[f])
        if not sc: return
        vs.append(pid)
        conn = self._get_conn()
        try: conn.execute(f"UPDATE products SET {', '.join(sc)} WHERE id=?", vs); conn.commit()
        finally: conn.close()

    def get_product(self, pid: str) -> dict | None:
        conn = self._get_conn()
        try:
            r = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            return dict(r) if r else None
        finally: conn.close()

    def delete_product(self, pid: str):
        conn = self._get_conn()
        try: conn.execute("DELETE FROM product_snapshots WHERE product_id=?", (pid,)); conn.execute("DELETE FROM products WHERE id=?", (pid,)); conn.commit()
        finally: conn.close()

    def search_products(self, keyword="", limit=100, offset=0) -> list[dict]:
        conn = self._get_conn()
        try:
            b = """SELECT id,name,cost,domestic_shipping,head_haul_cost,fixed_service_fee,tail_haul_cost,
                   freight_forwarder,selling_price_rmb,selling_price_usd,
                   target_profit_rate,promotion_reserve_rate,status,created_at,updated_at FROM products"""
            if keyword:
                p = f"%{keyword}%"
                rs = conn.execute(b+" WHERE name LIKE ? OR id LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?", (p,p,limit,offset)).fetchall()
            else:
                rs = conn.execute(b+" ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit,offset)).fetchall()
            return [dict(r) for r in rs]
        finally: conn.close()

    # ─── 快照 ────────────────────────────────────────────

    def save_snapshot(self, pid: str, data: dict, rules: dict = None, calc_results: dict = None):
        now = datetime.now().isoformat()
        # 在 data 中嵌入计算结果
        snap_data = dict(data)
        if calc_results:
            snap_data["_calculation_results"] = calc_results
        sj = json.dumps(snap_data, ensure_ascii=False)
        conn = self._get_conn()
        try:
            ex = conn.execute("SELECT id FROM product_snapshots WHERE product_id=?", (pid,)).fetchone()
            if ex is None:
                sid = str(uuid.uuid4())[:8]
                er = rules.get("exchange_rate") if rules else None
                hr = rules.get("head_haul_rate") if rules else None
                ff = rules.get("fixed_service_fee") if rules else None
                tc = rules.get("tail_haul_cost") if rules else None
                vd = rules.get("volume_divisor", VOLUME_DIVISOR)
                rv = rules.get("rule_version", CURRENT_RULE_VERSION)
                rs = json.dumps(rules, ensure_ascii=False) if rules else None
                conn.execute("""INSERT INTO product_snapshots (id,product_id,snapshot_data,
                    exchange_rate,head_haul_rate,fixed_service_fee,tail_haul_cost,
                    volume_divisor,rule_version,rule_snapshot,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, pid, sj, er, hr, ff, tc, vd, rv, rs, now))
                conn.commit()
        finally: conn.close()

    def get_snapshot(self, pid: str) -> dict | None:
        conn = self._get_conn()
        try:
            r = conn.execute("""SELECT snapshot_data,exchange_rate,head_haul_rate,fixed_service_fee,
                tail_haul_cost,volume_divisor,rule_version,rule_snapshot
                FROM product_snapshots WHERE product_id=?""", (pid,)).fetchone()
            if r:
                d = json.loads(r["snapshot_data"])
                d["_snapshot_exchange_rate"] = r["exchange_rate"]
                d["_snapshot_head_haul_rate"] = r["head_haul_rate"]
                d["_snapshot_fixed_service_fee"] = r["fixed_service_fee"]
                d["_snapshot_tail_haul_cost"] = r["tail_haul_cost"]
                d["_snapshot_volume_divisor"] = r["volume_divisor"] or VOLUME_DIVISOR
                d["_snapshot_rule_version"] = r["rule_version"]
                if r["rule_snapshot"]:
                    d["_snapshot_rule_full"] = json.loads(r["rule_snapshot"])
                return d
            return None
        finally: conn.close()

    def get_config(self, key: str, default=None) -> str | None:
        conn = self._get_conn()
        try:
            r = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            return r["value"] if r else default
        finally: conn.close()

    def set_config(self, key: str, value: str):
        conn = self._get_conn()
        try: conn.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", (key,value)); conn.commit()
        finally: conn.close()

    def get_all_config(self) -> dict:
        conn = self._get_conn()
        try: return {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM config").fetchall()}
        finally: conn.close()
