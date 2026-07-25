"""
SQLite 数据库管理模块 — Schema v2

表结构:
  schema_version        — 数据库版本（迁移用）
  business_rule_version  — 业务规则版本（独立管理）
  products              — 商品主表（+freight_forwarder）
  product_snapshots     — 首次保存快照（+rule_snapshot JSON）
  route_config          — 货代费率表
  config                — 全局配置键值对
"""

import sqlite3
import json
import uuid
import os
import shutil
from datetime import datetime

CURRENT_SCHEMA_VERSION = 2
CURRENT_RULE_VERSION = 2  # 业务规则版本
VOLUME_DIVISOR = 8000

DEFAULT_ROUTES = {
    "shenzhen": {"head_haul_rate": 80.0, "fixed_service_fee": 10.0, "description": "深圳货代"},
    "yiwu":     {"head_haul_rate": 100.0, "fixed_service_fee": 6.0, "description": "义乌货代"},
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version   INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS business_rule_version (
    version     INTEGER PRIMARY KEY,
    description TEXT DEFAULT '',
    applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id                  TEXT PRIMARY KEY,
    name                TEXT DEFAULT '',
    cost                REAL,
    domestic_shipping   REAL,
    net_weight          REAL,
    net_length          REAL,
    net_width           REAL,
    net_height          REAL,
    packaged_weight     REAL,
    packaged_length     REAL,
    packaged_width      REAL,
    packaged_height     REAL,
    freight_forwarder   TEXT DEFAULT NULL,
    head_haul_cost      REAL,
    fixed_service_fee   REAL,
    tail_haul_cost      REAL,
    shein_price         REAL,
    selling_price_rmb   REAL,
    selling_price_usd   REAL,
    target_profit_rate  REAL,
    promotion_reserve_rate REAL,
    notes               TEXT DEFAULT '',
    status              TEXT DEFAULT 'active',
    image_path          TEXT DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_snapshots (
    id                  TEXT PRIMARY KEY,
    product_id          TEXT NOT NULL UNIQUE,
    snapshot_data       TEXT NOT NULL,
    exchange_rate       REAL,
    head_haul_rate      REAL,
    fixed_service_fee   REAL,
    tail_haul_cost      REAL,
    volume_divisor      INTEGER DEFAULT 8000,
    rule_version        INTEGER DEFAULT 1,
    rule_snapshot       TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS route_config (
    forwarder       TEXT PRIMARY KEY,
    head_haul_rate  REAL NOT NULL,
    fixed_service_fee REAL NOT NULL,
    description     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

NUMERIC_FIELDS = [
    "cost", "domestic_shipping",
    "net_weight", "net_length", "net_width", "net_height",
    "packaged_weight", "packaged_length", "packaged_width", "packaged_height",
    "head_haul_cost", "fixed_service_fee", "tail_haul_cost",
    "shein_price", "selling_price_rmb", "selling_price_usd",
    "target_profit_rate", "promotion_reserve_rate",
]

DEFAULT_CONFIG = {
    "exchange_rate": "7.20",
    "default_tail_haul": "40.0",
}


class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "profit_accounting.db")
        self.db_path = db_path
        self._init_db()
        self._migrate_if_needed()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _backup_db(self):
        """迁移前备份数据库"""
        if os.path.exists(self.db_path):
            backup_path = self.db_path + f".backup_v{self._get_current_version()}"
            shutil.copy2(self.db_path, backup_path)
            return backup_path
        return None

    def _get_current_version(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            return row["version"] if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _add_column_if_missing(self, conn, table, column, col_type):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript(SCHEMA_SQL)
            existing = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()),
                )
            # 业务规则版本
            br_exists = conn.execute(
                "SELECT version FROM business_rule_version LIMIT 1"
            ).fetchone()
            if br_exists is None:
                conn.execute(
                    "INSERT INTO business_rule_version (version, description, applied_at) VALUES (?, ?, ?)",
                    (CURRENT_RULE_VERSION, "双货代规则：深圳(80/10)+义乌(100/6)", datetime.now().isoformat()),
                )
            # 默认配置
            for key, val in DEFAULT_CONFIG.items():
                conn.execute(
                    "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, val)
                )
            # 货代费率
            for fwd, rates in DEFAULT_ROUTES.items():
                conn.execute(
                    "INSERT OR IGNORE INTO route_config (forwarder, head_haul_rate, fixed_service_fee, description) VALUES (?, ?, ?, ?)",
                    (fwd, rates["head_haul_rate"], rates["fixed_service_fee"], rates["description"]),
                )
            conn.commit()
        finally:
            conn.close()

    def _migrate_if_needed(self):
        """按需迁移：v0/v1 → v2"""
        current = self._get_current_version()
        if current >= CURRENT_SCHEMA_VERSION:
            return

        backup = self._backup_db()
        conn = self._get_conn()
        try:
            conn.execute("BEGIN TRANSACTION")

            if current < 2:
                # v1 → v2：增加货代字段、规则快照JSON、route_config表、业务规则版本
                self._add_column_if_missing(conn, "products", "freight_forwarder", "TEXT DEFAULT NULL")
                self._add_column_if_missing(conn, "product_snapshots", "tail_haul_cost", "REAL")
                self._add_column_if_missing(conn, "product_snapshots", "volume_divisor", "INTEGER DEFAULT 8000")
                self._add_column_if_missing(conn, "product_snapshots", "rule_snapshot", "TEXT")

                # 确保 route_config 表存在
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS route_config (
                        forwarder TEXT PRIMARY KEY,
                        head_haul_rate REAL NOT NULL,
                        fixed_service_fee REAL NOT NULL,
                        description TEXT DEFAULT ''
                    )
                """)
                for fwd, rates in DEFAULT_ROUTES.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO route_config (forwarder, head_haul_rate, fixed_service_fee, description) VALUES (?, ?, ?, ?)",
                        (fwd, rates["head_haul_rate"], rates["fixed_service_fee"], rates["description"]),
                    )

                # 确保 business_rule_version 表存在
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS business_rule_version (
                        version INTEGER PRIMARY KEY,
                        description TEXT DEFAULT '',
                        applied_at TEXT NOT NULL
                    )
                """)
                br_exists = conn.execute("SELECT version FROM business_rule_version LIMIT 1").fetchone()
                if br_exists is None:
                    conn.execute(
                        "INSERT INTO business_rule_version (version, description, applied_at) VALUES (?, ?, ?)",
                        (CURRENT_RULE_VERSION, "双货代规则：深圳(80/10)+义乌(100/6)", datetime.now().isoformat()),
                    )

                # 更新 schema_version
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()),
                )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            if backup:
                # 迁移失败回滚：恢复备份
                shutil.copy2(backup, self.db_path)
            raise
        finally:
            conn.close()

    def get_schema_version(self) -> int:
        return self._get_current_version()

    def get_rule_version(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT version FROM business_rule_version ORDER BY version DESC LIMIT 1").fetchone()
            return row["version"] if row else CURRENT_RULE_VERSION
        except sqlite3.OperationalError:
            return CURRENT_RULE_VERSION
        finally:
            conn.close()

    # ─── 货代规则 ──────────────────────────────────────────

    def get_route_rates(self, forwarder: str) -> dict | None:
        """获取货代费率"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT head_haul_rate, fixed_service_fee FROM route_config WHERE forwarder = ?",
                (forwarder,),
            ).fetchone()
            return {"head_haul_rate": row["head_haul_rate"], "fixed_service_fee": row["fixed_service_fee"]} if row else None
        finally:
            conn.close()

    def get_all_routes(self) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM route_config").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ─── 商品 CRUD ──────────────────────────────────────────

    def create_product(self, data: dict) -> str:
        product_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO products (
                    id, name, cost, domestic_shipping,
                    net_weight, net_length, net_width, net_height,
                    packaged_weight, packaged_length, packaged_width, packaged_height,
                    freight_forwarder,
                    head_haul_cost, fixed_service_fee, tail_haul_cost,
                    shein_price, selling_price_rmb, selling_price_usd,
                    target_profit_rate, promotion_reserve_rate,
                    notes, status, image_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id, data.get("name", ""), data.get("cost"), data.get("domestic_shipping"),
                    data.get("net_weight"), data.get("net_length"), data.get("net_width"), data.get("net_height"),
                    data.get("packaged_weight"), data.get("packaged_length"), data.get("packaged_width"), data.get("packaged_height"),
                    data.get("freight_forwarder"),
                    data.get("head_haul_cost"), data.get("fixed_service_fee"), data.get("tail_haul_cost"),
                    data.get("shein_price"), data.get("selling_price_rmb"), data.get("selling_price_usd"),
                    data.get("target_profit_rate"), data.get("promotion_reserve_rate"),
                    data.get("notes", ""), data.get("status", "active"), data.get("image_path", ""),
                    now, now,
                ),
            )
            conn.commit()
            return product_id
        finally:
            conn.close()

    def update_product(self, product_id: str, data: dict):
        now = datetime.now().isoformat()
        data["updated_at"] = now
        set_clauses = []
        values = []
        for field in NUMERIC_FIELDS + ["name", "freight_forwarder", "notes", "status", "image_path", "updated_at"]:
            if field in data:
                set_clauses.append(f"{field} = ?")
                values.append(data[field])
        if not set_clauses:
            return
        values.append(product_id)
        sql = f"UPDATE products SET {', '.join(set_clauses)} WHERE id = ?"
        conn = self._get_conn()
        try:
            conn.execute(sql, values)
            conn.commit()
        finally:
            conn.close()

    def get_product(self, product_id: str) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_product(self, product_id: str):
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM product_snapshots WHERE product_id = ?", (product_id,))
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()
        finally:
            conn.close()

    def search_products(self, keyword="", limit=100, offset=0) -> list[dict]:
        conn = self._get_conn()
        try:
            base = """SELECT id, name, cost, domestic_shipping,
                             head_haul_cost, fixed_service_fee, tail_haul_cost,
                             freight_forwarder,
                             selling_price_rmb, selling_price_usd,
                             target_profit_rate, promotion_reserve_rate,
                             status, created_at, updated_at
                      FROM products"""
            if keyword:
                pattern = f"%{keyword}%"
                rows = conn.execute(
                    base + " WHERE name LIKE ? OR id LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (pattern, pattern, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    base + " ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_all_products(self, limit=200) -> list[dict]:
        return self.search_products(keyword="", limit=limit)

    # ─── 快照管理 ──────────────────────────────────────────

    def save_snapshot(self, product_id: str, data: dict, rules: dict = None):
        now = datetime.now().isoformat()
        snapshot_json = json.dumps(data, ensure_ascii=False)
        conn = self._get_conn()
        try:
            existing = conn.execute(
                "SELECT id FROM product_snapshots WHERE product_id = ?", (product_id,)
            ).fetchone()
            if existing is None:
                snap_id = str(uuid.uuid4())[:8]
                er = rules.get("exchange_rate") if rules else None
                hr = rules.get("head_haul_rate") if rules else None
                ff = rules.get("fixed_service_fee") if rules else None
                tc = rules.get("tail_haul_cost") if rules else None
                vd = rules.get("volume_divisor", VOLUME_DIVISOR)
                rv = rules.get("rule_version", CURRENT_RULE_VERSION)
                rs = json.dumps(rules, ensure_ascii=False) if rules else None
                conn.execute(
                    """INSERT INTO product_snapshots
                       (id, product_id, snapshot_data, exchange_rate, head_haul_rate,
                        fixed_service_fee, tail_haul_cost, volume_divisor,
                        rule_version, rule_snapshot, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (snap_id, product_id, snapshot_json, er, hr, ff, tc, vd, rv, rs, now),
                )
                conn.commit()
        finally:
            conn.close()

    def get_snapshot(self, product_id: str) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT snapshot_data, exchange_rate, head_haul_rate,
                          fixed_service_fee, tail_haul_cost, volume_divisor,
                          rule_version, rule_snapshot
                   FROM product_snapshots WHERE product_id = ?""",
                (product_id,),
            ).fetchone()
            if row:
                result = json.loads(row["snapshot_data"])
                result["_snapshot_exchange_rate"] = row["exchange_rate"]
                result["_snapshot_head_haul_rate"] = row["head_haul_rate"]
                result["_snapshot_fixed_service_fee"] = row["fixed_service_fee"]
                result["_snapshot_tail_haul_cost"] = row["tail_haul_cost"]
                result["_snapshot_volume_divisor"] = row["volume_divisor"] or VOLUME_DIVISOR
                result["_snapshot_rule_version"] = row["rule_version"]
                if row["rule_snapshot"]:
                    result["_snapshot_rule_full"] = json.loads(row["rule_snapshot"])
                return result
            return None
        finally:
            conn.close()

    # ─── 配置管理 ──────────────────────────────────────────

    def get_config(self, key: str, default=None) -> str | None:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def set_config(self, key: str, value: str):
        conn = self._get_conn()
        try:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
        finally:
            conn.close()

    def get_all_config(self) -> dict:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT key, value FROM config").fetchall()
            return {r["key"]: r["value"] for r in rows}
        finally:
            conn.close()
