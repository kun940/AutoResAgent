"""修改notifications表type列，添加order_created枚举值"""
import sys
from pathlib import Path

# 允许从脚本目录直接导入 _db
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import get_connection

conn = get_connection()
cursor = conn.cursor()

# 查看当前定义
cursor.execute("SHOW COLUMNS FROM notifications LIKE 'type'")
print("Before:", cursor.fetchone())

# 修改type列
cursor.execute("ALTER TABLE notifications MODIFY COLUMN type VARCHAR(50) NOT NULL")
conn.commit()

# 验证
cursor.execute("SHOW COLUMNS FROM notifications LIKE 'type'")
print("After:", cursor.fetchone())

conn.close()
print("Done!")