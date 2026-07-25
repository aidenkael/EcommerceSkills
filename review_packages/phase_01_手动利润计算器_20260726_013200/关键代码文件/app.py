"""
微智能商品利润管理 v0.1 — 入口

启动方式：
    python app.py

依赖：仅需 Python 标准库（tkinter, sqlite3, json, uuid, datetime）
"""

import sys
import os

# 确保模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from config.config_manager import ConfigManager
from ui.main_window import MainWindow


def main():
    db = DatabaseManager()
    cfg = ConfigManager(db)
    app = MainWindow(db, cfg)
    app.run()


if __name__ == "__main__":
    main()
