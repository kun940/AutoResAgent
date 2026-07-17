"""修改ticket_logs表action列，支持新的action值"""
import sys
from pathlib import Path

# 允许从脚本目录直接导入 _db
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import get_connection

conn = get_connection()
cursor = conn.cursor()

# 检查ticket_logs的action列
cursor.execute("SHOW COLUMNS FROM ticket_logs LIKE 'action'")
before = cursor.fetchone()
print("ticket_logs.action Before:", before)

if before and 'enum' in (before[1] or ''):
    cursor.execute("ALTER TABLE ticket_logs MODIFY COLUMN action VARCHAR(50) NOT NULL")
    conn.commit()
    cursor.execute("SHOW COLUMNS FROM ticket_logs LIKE 'action'")
    print("ticket_logs.action After:", cursor.fetchone())
else:
    print("ticket_logs.action already VARCHAR or no change needed")

conn.close()
print("Done!")
