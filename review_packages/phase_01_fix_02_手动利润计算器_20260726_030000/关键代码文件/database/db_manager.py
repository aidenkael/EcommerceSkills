"""
SQLite 数据库管理模块

表结构:
  schema_version    — 数据库版本（迁移用）
  products         — 商品主表（当前有效数据）
  product_snapshots — 第一次保存时的快照（含当时费率）
  config           — 配置键值对

规则版本: 1 (初始版)
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime


CURRENT_SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version   INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
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
    rule_version        INTEGER DEFAULT 1,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# 所有数值字段列表
NUMERIC_FIELDS = [
    "cost", "domestic_shipping",
    "net_weight", "net_length", "net_width", "net_height",
    "packaged_weight", "packaged_length", "packaged_width", "packaged_height",
    "head_haul_cost", "fixed_service_fee", "tail_haul_cost",
    "shein_price", "selling_price_rmb", "selling_price_usd",
    "target_profit_rate", "promotion_reserve_rate",
]

# 配置默认值（v1 基线：6元固定费 + 40元尾程）
DEFAULT_CONFIG = {
    "exchange_rate": "7.20",
    "head_haul_rate": "100.0",
    "fixed_service_fee": "6.0",
    "default_tail_haul": "40.0",
}


class DatabaseManager:
    """SQLite 数据库管理"""

    def __init__(self, db_path=None):
        if db_path is None:
            db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "profit_accounting.db")
        self.db_path = db_path
        self._init_db()
        self._migrate_config()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _add_column_if_missing(self, conn, table, column, col_type):
        """安全添加列（如果不存在）"""
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass  # 列已存在

    def _init_db(self):
        """建表 + 版本初始化 + 列迁移"""
        conn = self._get_conn()
        try:
            conn.executescript(SCHEMA_SQL)

            # 为旧版快照表补充新列（如果不存在）
            self._add_column_if_missing(conn, "product_snapshots", "exchange_rate", "REAL")
            self._add_column_if_missing(conn, "product_snapshots", "head_haul_rate", "REAL")
            self._add_column_if_missing(conn, "product_snapshots", "fixed_service_fee", "REAL")
            self._add_column_if_missing(conn, "product_snapshots", "rule_version", "INTEGER DEFAULT 1")

            # 检查 schema_version 是否已有记录
            existing = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()

            if existing is None:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()),
                )

            # 填入默认配置（仅当 key 不存在时）
            for key, val in DEFAULT_CONFIG.items():
                conn.execute(
                    "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                    (key, val),
                )
            conn.commit()
        finally:
            conn.close()

    def _migrate_config(self):
        """安全迁移：仅在新数据库首次初始化时生效。不会覆盖用户已有设置。"""
        conn = self._get_conn()
        try:
            # 检查是否已执行过迁移
            migrated = conn.execute(
                "SELECT value FROM config WHERE key = '_config_migrated_v1'"
            ).fetchone()
            if migrated and migrated["value"] == "1":
                return

            # 首次运行：如果旧版数据库中有出厂默认值(36/0)且用户尚未修改，则更新
            old_factory = {"fixed_service_fee": "36.0", "default_tail_haul": "0.0"}
            for key, old_val in old_factory.items():
                current = conn.execute(
                    "SELECT value FROM config WHERE key = ?", (key,)
                ).fetchone()
                if current and current["value"] == old_val:
                    # 仍是旧出厂默认值 → 升级到新默认值
                    conn.execute(
                        "UPDATE config SET value = ? WHERE key = ?",
                        (DEFAULT_CONFIG[key], key),
                    )

            # 标记已迁移（防止重复执行）
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES ('_config_migrated_v1', '1')"
            )
            conn.commit()
        finally:
            conn.close()

    def get_schema_version(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            return row["version"] if row else 0
        finally:
            conn.close()

    # ─── 商品 CRUD ──────────────────────────────────────────

    def create_product(self, data: dict) -> str:
        """创建新商品，返回商品ID"""
        product_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO products (
                    id, name, cost, domestic_shipping,
                    net_weight, net_length, net_width, net_height,
                    packaged_weight, packaged_length, packaged_width, packaged_height,
                    head_haul_cost, fixed_service_fee, tail_haul_cost,
                    shein_price, selling_price_rmb, selling_price_usd,
                    target_profit_rate, promotion_reserve_rate,
                    notes, status, image_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product_id,
                    data.get("name", ""),
                    data.get("cost"),
                    data.get("domestic_shipping"),
                    data.get("net_weight"),
                    data.get("net_length"),
                    data.get("net_width"),
                    data.get("net_height"),
                    data.get("packaged_weight"),
                    data.get("packaged_length"),
                    data.get("packaged_width"),
                    data.get("packaged_height"),
                    data.get("head_haul_cost"),
                    data.get("fixed_service_fee"),
                    data.get("tail_haul_cost"),
                    data.get("shein_price"),
                    data.get("selling_price_rmb"),
                    data.get("selling_price_usd"),
                    data.get("target_profit_rate"),
                    data.get("promotion_reserve_rate"),
                    data.get("notes", ""),
                    data.get("status", "active"),
                    data.get("image_path", ""),
                    now, now,
                ),
            )
            conn.commit()
            return product_id
        finally:
            conn.close()

    def update_product(self, product_id: str, data: dict):
        """更新商品数据"""
        now = datetime.now().isoformat()
        data["updated_at"] = now

        set_clauses = []
        values = []
        for field in NUMERIC_FIELDS + ["name", "notes", "status", "image_path", "updated_at"]:
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
        """获取单个商品"""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_product(self, product_id: str):
        """删除商品及其快照"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM product_snapshots WHERE product_id = ?", (product_id,))
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()
        finally:
            conn.close()

    def search_products(self, keyword="", limit=100, offset=0) -> list[dict]:
        """搜索商品（按名称或ID），返回含物流成本的完整数据供历史列表使用"""
        conn = self._get_conn()
        try:
            base_sql = """SELECT id, name, cost, domestic_shipping,
                                 head_haul_cost, fixed_service_fee, tail_haul_cost,
                                 selling_price_rmb, selling_price_usd,
                                 target_profit_rate, promotion_reserve_rate,
                                 status, created_at, updated_at
                          FROM products"""
            if keyword:
                pattern = f"%{keyword}%"
                rows = conn.execute(
                    base_sql + " WHERE name LIKE ? OR id LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (pattern, pattern, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    base_sql + " ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_all_products(self, limit=200) -> list[dict]:
        return self.search_products(keyword="", limit=limit)

    # ─── 快照管理 ──────────────────────────────────────────

    def save_snapshot(self, product_id: str, data: dict, rules: dict = None):
        """
        保存第一次推算快照（如果已存在则跳过）

        Args:
            product_id: 商品ID
            data: 商品数据dict
            rules: 当时的费率规则 dict，如 {'exchange_rate': 7.2, 'head_haul_rate': 100.0, ...}
        """
        now = datetime.now().isoformat()
        snapshot_json = json.dumps(data, ensure_ascii=False)

        conn = self._get_conn()
        try:
            existing = conn.execute(
                "SELECT id FROM product_snapshots WHERE product_id = ?", (product_id,)
            ).fetchone()
            if existing is None:
                snap_id = str(uuid.uuid4())[:8]
                ex_rate = rules.get("exchange_rate") if rules else None
                hd_rate = rules.get("head_haul_rate") if rules else None
                fx_fee = rules.get("fixed_service_fee") if rules else None
                conn.execute(
                    """INSERT INTO product_snapshots
                       (id, product_id, snapshot_data, exchange_rate, head_haul_rate,
                        fixed_service_fee, rule_version, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (snap_id, product_id, snapshot_json, ex_rate, hd_rate, fx_fee,
                     CURRENT_SCHEMA_VERSION, now),
                )
                conn.commit()
        finally:
            conn.close()

    def get_snapshot(self, product_id: str) -> dict | None:
        """获取快照数据（包含费率信息）"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT snapshot_data, exchange_rate, head_haul_rate,
                          fixed_service_fee, rule_version
                   FROM product_snapshots WHERE product_id = ?""",
                (product_id,),
            ).fetchone()
            if row:
                result = json.loads(row["snapshot_data"])
                result["_snapshot_exchange_rate"] = row["exchange_rate"]
                result["_snapshot_head_haul_rate"] = row["head_haul_rate"]
                result["_snapshot_fixed_service_fee"] = row["fixed_service_fee"]
                result["_snapshot_rule_version"] = row["rule_version"]
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
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
            )
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
