"""执行 v1.1 数据库迁移脚本"""
import pymysql

def run_migration():
    conn = pymysql.connect(
        host='localhost', port=3306, user='root',
        password='Lkj070329', database='complaint_agent',
        charset='utf8mb4',
    )
    cursor = conn.cursor()

    with open('scripts/migration_v1.1.sql', 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # 按分号分割，过滤空行和纯注释行
    statements = []
    current = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        current.append(line)
        if stripped.endswith(';'):
            stmt = '\n'.join(current).strip()
            if stmt and stmt != ';':
                statements.append(stmt.rstrip(';'))
            current = []

    for i, stmt in enumerate(statements, 1):
        try:
            cursor.execute(stmt)
            conn.commit()
            preview = stmt[:70].replace('\n', ' ')
            print(f'[{i}/{len(statements)}] OK: {preview}...')
        except Exception as e:
            err_msg = str(e)[:100]
            preview = stmt[:70].replace('\n', ' ')
            print(f'[{i}/{len(statements)}] ERROR: {err_msg}')
            print(f'  SQL: {preview}...')

    # 验证
    cursor.execute('SHOW TABLES')
    tables = [r[0] for r in cursor.fetchall()]
    print(f'\nAll tables ({len(tables)}): {tables}')

    for table in ['service_orders', 'quality_trace_index', 'order_mapping_rules']:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'{table}: {count} rows')

    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='complaint_agent' AND TABLE_NAME='tickets' AND COLUMN_NAME='order_status'")
    if cursor.fetchone():
        print('tickets.order_status: EXISTS')
    else:
        print('tickets.order_status: MISSING')

    conn.close()
    print('\nMigration completed!')

if __name__ == '__main__':
    run_migration()
