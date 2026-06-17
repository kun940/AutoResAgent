"""修改notifications表type列，添加order_created枚举值"""
import pymysql

conn = pymysql.connect(
    host='localhost', port=3306, user='root',
    password='Lkj070329', database='complaint_agent', charset='utf8mb4'
)
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
