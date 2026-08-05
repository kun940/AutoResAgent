"""脚本共用数据库连接工厂。

从 config/.env 读取数据库配置，避免在脚本中硬编码凭据。
所有需要连接 MySQL 的脚本统一调用 get_connection()。
"""
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / "config" / ".env")


def get_connection() -> pymysql.connections.Connection:
    """返回一个已连接的 pymysql 连接。

    缺少 DB_PASSWORD 时直接退出，避免误连或暴露配置问题。
    """
    password = os.getenv("DB_PASSWORD", "")
    if not password:
        print("ERROR: DB_PASSWORD 未设置，请检查 config/.env", file=sys.stderr)
        sys.exit(1)

    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=password,
        database=os.getenv("DB_NAME", "complaint_agent"),
        charset=os.getenv("DB_CHARSET", "utf8mb4"),
    )
