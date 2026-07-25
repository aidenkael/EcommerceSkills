"""
SQLite 数据库管理 — Schema v3

迁移规则：
- 新数据库：直接创建完整 v3 schema，不备份不迁移
- 旧数据库：先只读检查→关闭→备份→事务迁移→提交/回滚
- 当前商品状态与首次快照在同一事务中保存
"""

import sqlite3, json, uuid, os, shutil
from datetime import datetime

CURRENT_SCHEMA_VERSION = 3
CURRENT_RULE_VERSION = 2
CALCULATION_SCHEMA_VERSION = 1
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
    current_rule_snapshot TEXT, current_calculation_results TEXT,
    calculation_schema_version INTEGER DEFAULT 1, calculated_at TEXT,
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
            if old_version > CURRENT_SCHEMA_VERSION:
                raise RuntimeError(
                    f"数据库版本 {old_version} 高于程序支持的版本 {CURRENT_SCHEMA_VERSION}，"
                    "请使用更新版本的程序。"
                )
            if old_version < CURRENT_SCHEMA_VERSION:
                self._migrate_from(old_version)
            else:
                self._init_db()
                self._seed_current_data()
        else:
            self._init_db()
            self._seed_current_data()
        self._validate_database_file()

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
        """从旧版本迁移到当前版本，失败时恢复原数据库。"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.db_path + f".backup_v{old_version}_to_v{CURRENT_SCHEMA_VERSION}_{ts}.db"
        shutil.copy2(self.db_path, backup_path)

        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN TRANSACTION")
            self._apply_migration(conn, old_version)
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            conn.close()
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, self.db_path)
            raise
        finally:
            try:
                conn.close()
            except sqlite3.ProgrammingError:
                pass

    def _apply_migration(self, conn, old_version: int):
        """在一个已开启的事务中完成结构、种子和旧状态回填。"""
        for stmt in [
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS business_rule_version (version INTEGER PRIMARY KEY, description TEXT DEFAULT '', applied_at TEXT NOT NULL)",
            """CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY, name TEXT DEFAULT '', cost REAL, domestic_shipping REAL,
                net_weight REAL, net_length REAL, net_width REAL, net_height REAL,
                packaged_weight REAL, packaged_length REAL, packaged_width REAL, packaged_height REAL,
                freight_forwarder TEXT DEFAULT NULL,
                head_haul_cost REAL, fixed_service_fee REAL, tail_haul_cost REAL,
                shein_price REAL, selling_price_rmb REAL, selling_price_usd REAL,
                target_profit_rate REAL, promotion_reserve_rate REAL,
                current_rule_snapshot TEXT, current_calculation_results TEXT,
                calculation_schema_version INTEGER DEFAULT 1, calculated_at TEXT,
                notes TEXT DEFAULT '', status TEXT DEFAULT 'active', image_path TEXT DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS product_snapshots (
                id TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE,
                snapshot_data TEXT NOT NULL, exchange_rate REAL, head_haul_rate REAL,
                fixed_service_fee REAL, tail_haul_cost REAL, volume_divisor INTEGER DEFAULT 8000,
                rule_version INTEGER DEFAULT 1, rule_snapshot TEXT, created_at TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE)""",
            "CREATE TABLE IF NOT EXISTS route_config (forwarder TEXT PRIMARY KEY, head_haul_rate REAL NOT NULL, fixed_service_fee REAL NOT NULL, description TEXT DEFAULT '')",
            "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        ]:
            conn.execute(stmt)

        product_columns = {
            "name": "TEXT DEFAULT ''",
            "cost": "REAL",
            "domestic_shipping": "REAL",
            "net_weight": "REAL",
            "net_length": "REAL",
            "net_width": "REAL",
            "net_height": "REAL",
            "packaged_weight": "REAL",
            "packaged_length": "REAL",
            "packaged_width": "REAL",
            "packaged_height": "REAL",
            "freight_forwarder": "TEXT DEFAULT NULL",
            "head_haul_cost": "REAL",
            "fixed_service_fee": "REAL",
            "tail_haul_cost": "REAL",
            "shein_price": "REAL",
            "selling_price_rmb": "REAL",
            "selling_price_usd": "REAL",
            "target_profit_rate": "REAL",
            "promotion_reserve_rate": "REAL",
            "current_rule_snapshot": "TEXT",
            "current_calculation_results": "TEXT",
            "calculation_schema_version": f"INTEGER DEFAULT {CALCULATION_SCHEMA_VERSION}",
            "calculated_at": "TEXT",
            "notes": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT 'active'",
            "image_path": "TEXT DEFAULT ''",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        snapshot_columns = {
            "exchange_rate": "REAL",
            "head_haul_rate": "REAL",
            "fixed_service_fee": "REAL",
            "tail_haul_cost": "REAL",
            "volume_divisor": "INTEGER DEFAULT 8000",
            "rule_version": "INTEGER DEFAULT 1",
            "rule_snapshot": "TEXT",
            "created_at": "TEXT",
        }
        self._require_columns(conn, "products", {"id"})
        self._require_columns(
            conn, "product_snapshots", {"id", "product_id", "snapshot_data"}
        )
        for column, column_type in product_columns.items():
            self._add_column_if_missing(conn, "products", column, column_type)
        for column, column_type in snapshot_columns.items():
            self._add_column_if_missing(conn, "product_snapshots", column, column_type)

        for fwd, rates in DEFAULT_ROUTES.items():
            conn.execute(
                "INSERT OR IGNORE INTO route_config VALUES (?,?,?,?)",
                (fwd, rates["head_haul_rate"], rates["fixed_service_fee"], rates["description"]),
            )
        conn.execute(
            "INSERT OR IGNORE INTO business_rule_version (version, description, applied_at) VALUES (?,?,?)",
            (CURRENT_RULE_VERSION, "双货代规则", datetime.now().isoformat()),
        )
        for key, value in DEFAULT_CONFIG.items():
            conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (key, value))

        self._backfill_current_state(conn)
        self._validate_migrated_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?,?)",
            (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()),
        )

    def _backfill_current_state(self, conn):
        """从旧首次快照回填缺失的当前状态；无法可靠恢复的字段保持缺失。"""
        rows = conn.execute(
            """SELECT p.id, p.current_rule_snapshot, p.current_calculation_results,
                      s.snapshot_data, s.rule_snapshot
               FROM products p
               LEFT JOIN product_snapshots s ON s.product_id = p.id"""
        ).fetchall()
        for row in rows:
            rule_json = row["current_rule_snapshot"]
            calc_json = row["current_calculation_results"]
            if rule_json is None and row["rule_snapshot"]:
                rule_json = row["rule_snapshot"]
            if calc_json is None and row["snapshot_data"]:
                try:
                    snapshot_data = json.loads(row["snapshot_data"])
                    calculation_results = snapshot_data.get("_calculation_results")
                    if isinstance(calculation_results, dict):
                        calc_json = json.dumps(calculation_results, ensure_ascii=False)
                except (TypeError, ValueError):
                    pass
            if rule_json is not None or calc_json is not None:
                conn.execute(
                    """UPDATE products
                       SET current_rule_snapshot=COALESCE(current_rule_snapshot, ?),
                           current_calculation_results=COALESCE(current_calculation_results, ?),
                           calculation_schema_version=COALESCE(calculation_schema_version, ?)
                       WHERE id=?""",
                    (rule_json, calc_json, CALCULATION_SCHEMA_VERSION, row["id"]),
                )

    @staticmethod
    def _table_columns(conn, table):
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}

    def _require_columns(self, conn, table, required):
        missing = required - self._table_columns(conn, table)
        if missing:
            raise RuntimeError(f"{table} 缺少不可安全推断的关键字段: {sorted(missing)}")

    def _validate_migrated_schema(self, conn):
        required_product_columns = {
            "id", "name", "cost", "domestic_shipping",
            "net_weight", "net_length", "net_width", "net_height",
            "packaged_weight", "packaged_length", "packaged_width", "packaged_height",
            "freight_forwarder", "head_haul_cost", "fixed_service_fee", "tail_haul_cost",
            "shein_price", "selling_price_rmb", "selling_price_usd",
            "target_profit_rate", "promotion_reserve_rate",
            "current_rule_snapshot", "current_calculation_results",
            "calculation_schema_version", "calculated_at",
            "notes", "status", "image_path", "created_at", "updated_at",
        }
        required_snapshot_columns = {
            "id", "product_id", "snapshot_data", "exchange_rate", "head_haul_rate",
            "fixed_service_fee", "tail_haul_cost", "volume_divisor", "rule_version",
            "rule_snapshot",
        }
        self._require_columns(conn, "products", required_product_columns)
        self._require_columns(conn, "product_snapshots", required_snapshot_columns)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"数据库完整性检查失败: {integrity}")
        foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError("数据库外键检查失败")

    def _validate_database_file(self):
        conn = self._get_conn()
        try:
            self._validate_migrated_schema(conn)
        finally:
            conn.close()

    def _init_db(self):
        """建表（不写版本号，不写种子数据）"""
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def _seed_current_data(self):
        """确保当前版本号、配置和货代种子存在。"""
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

    @staticmethod
    def _json_or_none(value):
        return json.dumps(value, ensure_ascii=False) if value is not None else None

    @staticmethod
    def _decode_product(row):
        if row is None:
            return None
        data = dict(row)
        for column, key in [
            ("current_rule_snapshot", "_current_rule_snapshot"),
            ("current_calculation_results", "_current_calculation_results"),
        ]:
            raw = data.get(column)
            if raw:
                try:
                    data[key] = json.loads(raw)
                except (TypeError, ValueError):
                    data[key] = None
            else:
                data[key] = None
        return data

    def save_product_state(
        self,
        data: dict,
        rules: dict,
        calc_results: dict,
        pid: str | None = None,
    ) -> str:
        """原子保存商品当前状态；新商品同时创建不可变首次快照。"""
        now = datetime.now().isoformat()
        rule_json = self._json_or_none(rules)
        calc_json = self._json_or_none(calc_results)
        conn = self._get_conn()
        try:
            conn.execute("BEGIN TRANSACTION")
            if pid is None:
                pid = str(uuid.uuid4())[:8]
                self._insert_product(conn, pid, data, now, rule_json, calc_json)
                self._insert_initial_snapshot(conn, pid, data, rules, calc_results, now)
            else:
                self._update_product_in_conn(
                    conn, pid, data, now, rule_json, calc_json
                )
            conn.execute("COMMIT")
            return pid
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    def _insert_product(self, conn, pid, data, now, rule_json=None, calc_json=None):
        conn.execute("""INSERT INTO products (id,name,cost,domestic_shipping,
            net_weight,net_length,net_width,net_height,
            packaged_weight,packaged_length,packaged_width,packaged_height,
            freight_forwarder,head_haul_cost,fixed_service_fee,tail_haul_cost,
            shein_price,selling_price_rmb,selling_price_usd,
            target_profit_rate,promotion_reserve_rate,
            current_rule_snapshot,current_calculation_results,
            calculation_schema_version,calculated_at,
            notes,status,image_path,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, data.get("name",""), data.get("cost"), data.get("domestic_shipping"),
             data.get("net_weight"), data.get("net_length"), data.get("net_width"), data.get("net_height"),
             data.get("packaged_weight"), data.get("packaged_length"), data.get("packaged_width"), data.get("packaged_height"),
             data.get("freight_forwarder"), data.get("head_haul_cost"), data.get("fixed_service_fee"), data.get("tail_haul_cost"),
             data.get("shein_price"), data.get("selling_price_rmb"), data.get("selling_price_usd"),
             data.get("target_profit_rate"), data.get("promotion_reserve_rate"),
             rule_json, calc_json, CALCULATION_SCHEMA_VERSION, now,
             data.get("notes",""), data.get("status","active"), data.get("image_path",""), now, now))

    def _update_product_in_conn(self, conn, pid, data, now, rule_json, calc_json):
        assignments = []
        values = []
        for field in NUMERIC_FIELDS + ["name", "freight_forwarder", "notes", "status", "image_path"]:
            if field in data:
                assignments.append(f"{field}=?")
                values.append(data[field])
        assignments.extend([
            "current_rule_snapshot=?",
            "current_calculation_results=?",
            "calculation_schema_version=?",
            "calculated_at=?",
            "updated_at=?",
        ])
        values.extend([rule_json, calc_json, CALCULATION_SCHEMA_VERSION, now, now, pid])
        conn.execute(f"UPDATE products SET {', '.join(assignments)} WHERE id=?", values)

    def _insert_initial_snapshot(self, conn, pid, data, rules, calc_results, now):
        if conn.execute(
            "SELECT 1 FROM product_snapshots WHERE product_id=?", (pid,)
        ).fetchone():
            return
        snap_data = dict(data)
        if calc_results is not None:
            snap_data["_calculation_results"] = calc_results
        conn.execute(
            """INSERT INTO product_snapshots (id,product_id,snapshot_data,
               exchange_rate,head_haul_rate,fixed_service_fee,tail_haul_cost,
               volume_divisor,rule_version,rule_snapshot,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(uuid.uuid4())[:8],
                pid,
                json.dumps(snap_data, ensure_ascii=False),
                rules.get("exchange_rate") if rules else None,
                rules.get("head_haul_rate") if rules else None,
                rules.get("fixed_service_fee") if rules else None,
                rules.get("tail_haul_cost") if rules else None,
                rules.get("volume_divisor", VOLUME_DIVISOR) if rules else VOLUME_DIVISOR,
                rules.get("rule_version", CURRENT_RULE_VERSION) if rules else CURRENT_RULE_VERSION,
                self._json_or_none(rules),
                now,
            ),
        )

    def create_product(self, data: dict) -> str:
        pid = str(uuid.uuid4())[:8]; now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            self._insert_product(conn, pid, data, now)
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
            return self._decode_product(r)
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
                   target_profit_rate,promotion_reserve_rate,
                   current_rule_snapshot,current_calculation_results,
                   calculation_schema_version,calculated_at,
                   status,created_at,updated_at FROM products"""
            if keyword:
                p = f"%{keyword}%"
                rs = conn.execute(b+" WHERE name LIKE ? OR id LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?", (p,p,limit,offset)).fetchall()
            else:
                rs = conn.execute(b+" ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit,offset)).fetchall()
            return [self._decode_product(r) for r in rs]
        finally: conn.close()

    # ─── 快照 ────────────────────────────────────────────

    def save_snapshot(self, pid: str, data: dict, rules: dict = None, calc_results: dict = None):
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            self._insert_initial_snapshot(conn, pid, data, rules, calc_results, now)
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
