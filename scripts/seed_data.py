import asyncio
import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiomysql
import bcrypt
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "complaint_agent")
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")




async def seed_users(conn):
    users = [
        ("admin", "admin123", "admin", "总经理办公室"),
        ("zhangsan", "staff123", "frontline_staff", "售后服务部"),
        ("lisi", "manager123", "department_manager", "技术质量部"),
        ("wangwu", "gm123", "general_manager", "总经理办公室"),
    ]
    async with conn.cursor() as cur:
        for username, password, role, dept in users:
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            await cur.execute(
                "INSERT IGNORE INTO `users` (username, password_hash, role, department) VALUES (%s, %s, %s, %s)",
                (username, hashed, role, dept)
            )
    print("  用户数据: 4条")


async def seed_routing_rules(conn):
    rules = [
        ("Low_Priority", "frontline_staff", "售后服务部", 48, "常规缺件/操作失误，派发至一线员工"),
        ("Medium_Priority", "department_manager", "技术质量部", 24, "核心部件损坏/疑似批次缺陷，路由至部门经理"),
        ("High_Priority", "general_manager", "总经理办公室", 2, "涉及人身财产安全/群体性客诉风险，直达总经理看板"),
    ]
    async with conn.cursor() as cur:
        for urgency, role, dept, sla, desc in rules:
            await cur.execute(
                "INSERT IGNORE INTO `routing_rules` (urgency_level, target_role, target_department, sla_hours, description) VALUES (%s, %s, %s, %s, %s)",
                (urgency, role, dept, sla, desc)
            )
    print("  路由规则: 3条")


async def seed_escalation_rules(conn):
    rules = [
        ("Low_Priority", "Medium_Priority", "SLA超时48小时自动升级", 48),
        ("Medium_Priority", "High_Priority", "SLA超时24小时自动升级", 24),
    ]
    async with conn.cursor() as cur:
        for from_l, to_l, cond, hours in rules:
            await cur.execute(
                "INSERT IGNORE INTO `escalation_rules` (from_level, to_level, trigger_condition, auto_escalate_hours) VALUES (%s, %s, %s, %s)",
                (from_l, to_l, cond, hours)
            )
    print("  升级规则: 2条")


async def seed_sop_knowledge(conn):
    sops = [
        ("Missing_Parts", "配件缺失补发流程",
         "1. 确认缺失配件名称和数量\n2. 核对订单明细\n3. 安排补发物流\n4. 预计3-5个工作日送达\n5. 补发后短信通知客户",
         "Low_Priority", '["缺件", "缺失", "少件", "螺丝", "配件"]'),
        ("Hardware_Thermal_Runaway", "设备过热/冒烟紧急处置",
         "1. 立即切断设备总电源\n2. 人员远离设备，保持通风\n3. 严禁用水灭火\n4. 拨打售后紧急热线400-XXX-XXXX\n5. 等待技术人员到场处理",
         "High_Priority", '["冒烟", "过热", "烧焦", "发热", "起火"]'),
        ("Electrical_Leakage", "漏电紧急处置SOP",
         "1. 立即切断总闸并远离设备\n2. 确保人员安全撤离\n3. 拨打售后紧急热线\n4. 严禁触碰设备任何部位",
         "High_Priority", '["漏电", "触电", "带电", "麻手"]'),
        ("Hardware_Malfunction", "设备频繁重启排查指引",
         "1. 检查电源连接是否稳定\n2. 确认使用环境温度是否过高\n3. 记录重启频率和时间段\n4. 联系技术支持安排远程诊断",
         "Medium_Priority", '["重启", "死机", "蓝屏", "卡顿", "频繁"]'),
        ("Software_Bug", "软件崩溃恢复操作",
         "1. 记录崩溃前的操作步骤和错误信息\n2. 尝试重启软件并检查更新\n3. 清除缓存和临时文件\n4. 如问题持续，联系技术支持远程诊断\n5. 必要时提供软件重装包",
         "Medium_Priority", '["崩溃", "软件", "闪退", "报错", "程序"]'),
        ("Batch_Defect", "疑似批次缺陷上报流程",
         "1. 记录产品批次号\n2. 收集同批次其他客户反馈\n3. 上报技术质量部\n4. 启动批次追溯程序\n5. 48小时内给出初步结论",
         "Medium_Priority", '["批次", "批量", "同一批", "多台"]'),
    ]
    async with conn.cursor() as cur:
        for cat, title, content, urgency, keywords in sops:
            await cur.execute(
                "INSERT IGNORE INTO `sop_knowledge_base` (issue_category, title, content, urgency_level, keywords) VALUES (%s, %s, %s, %s, %s)",
                (cat, title, content, urgency, keywords)
            )
    print("  SOP知识: 6条")


async def seed_warranty_records(conn):
    records = [
        ("SN-PMV2-001", "Pro-Max-V2", "X11", date(2025, 6, 1), date(2027, 6, 1), "张三", "JD9988776655"),
        ("SN-PMV2-002", "Pro-Max-V2", "X12", date(2025, 8, 15), date(2027, 8, 15), "李四", "JD5566778899"),
        ("SN-STD-V1-001", "Std-V1", "A05", date(2024, 3, 10), date(2026, 3, 10), "王五", "JD1122334455"),
    ]
    async with conn.cursor() as cur:
        for sn, model, batch, start, end, customer, order in records:
            await cur.execute(
                "INSERT IGNORE INTO `warranty_records` (sn_code, model_number, batch_code, warranty_start, warranty_end, customer_name, order_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (sn, model, batch, start, end, customer, order)
            )
    print("  质保记录: 3条")


async def seed_order_mapping_rules(conn):
    """初始化出单映射规则数据（如果数据库中还没有的话）"""
    # 先检查是否已有数据
    async with conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM `order_mapping_rules`")
        count = (await cur.fetchone())[0]
        if count > 0:
            print(f"  出单映射规则: 已存在{count}条，跳过插入")
            return

    rules = [
        # Missing_Parts -> Replacement (补发单, 售后服务部)
        ("Missing_Parts",            "Low_Priority",    "Replacement",     "售后服务部", 72, 10, "缺件-低优先级-补发单"),
        ("Missing_Parts",            "Medium_Priority", "Replacement",     "售后服务部", 48, 20, "缺件-中优先级-补发单"),
        ("Missing_Parts",            "High_Priority",   "Replacement",     "售后服务部", 24, 30, "缺件-高优先级-补发单"),
        # Operation_Error -> Tech_Support (技术支援单, 技术支持部)
        ("Operation_Error",          "Low_Priority",    "Tech_Support",   "技术支持部", 72, 10, "操作失误-低优先级-技术支援单"),
        ("Operation_Error",          "Medium_Priority", "Tech_Support",   "技术支持部", 48, 20, "操作失误-中优先级-技术支援单"),
        ("Operation_Error",          "High_Priority",   "Tech_Support",   "技术支持部", 24, 30, "操作失误-高优先级-技术支援单"),
        # Software_Bug -> Tech_Support (技术支援单, 技术支持部)
        ("Software_Bug",             "Low_Priority",    "Tech_Support",   "技术支持部", 72, 10, "软件缺陷-低优先级-技术支援单"),
        ("Software_Bug",             "Medium_Priority", "Tech_Support",   "技术支持部", 48, 20, "软件缺陷-中优先级-技术支援单"),
        ("Software_Bug",             "High_Priority",   "Tech_Support",   "技术支持部", 24, 30, "软件缺陷-高优先级-技术支援单"),
        # Hardware_Malfunction -> Repair (维修单, 技术维修部)
        ("Hardware_Malfunction",     "Low_Priority",    "Repair",         "技术维修部", 120, 10, "硬件故障-低优先级-维修单"),
        ("Hardware_Malfunction",     "Medium_Priority", "Repair",         "技术维修部", 72,  20, "硬件故障-中优先级-维修单"),
        ("Hardware_Malfunction",     "High_Priority",   "Repair",         "技术维修部", 24,  30, "硬件故障-高优先级-维修单"),
        # Hardware_Thermal_Runaway -> Repair (维修单, 技术维修部)
        ("Hardware_Thermal_Runaway", "Low_Priority",    "Repair",         "技术维修部", 72,  10, "热失控-低优先级-维修单"),
        ("Hardware_Thermal_Runaway", "Medium_Priority",  "Repair",         "技术维修部", 24,  20, "热失控-中优先级-维修单"),
        ("Hardware_Thermal_Runaway", "High_Priority",    "Repair",         "技术维修部", 4,   30, "热失控-高优先级-维修单"),
        # Electrical_Leakage -> Repair (维修单, 技术维修部)
        ("Electrical_Leakage",       "Low_Priority",    "Repair",         "技术维修部", 72,  10, "漏电-低优先级-维修单"),
        ("Electrical_Leakage",       "Medium_Priority", "Repair",         "技术维修部", 24,  20, "漏电-中优先级-维修单"),
        ("Electrical_Leakage",       "High_Priority",   "Repair",         "技术维修部", 4,   30, "漏电-高优先级-维修单"),
        # Batch_Defect -> Return_Exchange (退换单, 售后服务部)
        ("Batch_Defect",             "Medium_Priority", "Return_Exchange", "售后服务部", 48, 20, "批次缺陷-中优先级-退换单"),
        ("Batch_Defect",             "High_Priority",   "Return_Exchange", "售后服务部", 24, 30, "批次缺陷-高优先级-退换单"),
        # Safety_Hazard -> Return_Exchange (退换单, 售后服务部)
        ("Safety_Hazard",            "Low_Priority",    "Return_Exchange", "售后服务部", 48, 10, "安全隐患-低优先级-退换单"),
        ("Safety_Hazard",            "Medium_Priority", "Return_Exchange", "售后服务部", 24, 20, "安全隐患-中优先级-退换单"),
        ("Safety_Hazard",            "High_Priority",   "Return_Exchange", "售后服务部", 4,  30, "安全隐患-高优先级-退换单"),
        # Batch_Defect -> QC (质检单, 质量管理部)
        ("Batch_Defect",             "Medium_Priority", "QC",              "质量管理部", 48, 15, "批次缺陷-中优先级-质检单"),
        ("Batch_Defect",             "High_Priority",   "QC",              "质量管理部", 24, 25, "批次缺陷-高优先级-质检单"),
        # Safety_Hazard -> QC (质检单, 质量管理部)
        ("Safety_Hazard",            "Low_Priority",    "QC",              "质量管理部", 48, 5,  "安全隐患-低优先级-质检单"),
        ("Safety_Hazard",            "Medium_Priority", "QC",              "质量管理部", 24, 15, "安全隐患-中优先级-质检单"),
        ("Safety_Hazard",            "High_Priority",   "QC",              "质量管理部", 4,  25, "安全隐患-高优先级-质检单"),
    ]
    async with conn.cursor() as cur:
        for issue_cat, urgency, order_type, dept, sla, priority, desc in rules:
            await cur.execute(
                "INSERT IGNORE INTO `order_mapping_rules` (issue_category, urgency_level, order_type, department, sla_hours, priority, description) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (issue_cat, urgency, order_type, dept, sla, priority, desc)
            )
    print("  出单映射规则: 27条")


async def main():
    print("=" * 50)
    print("客诉自动回复出单智能体 - 种子数据插入")
    print("=" * 50)
    print(f"MySQL: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print()

    conn = await aiomysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        db=DB_NAME, charset=DB_CHARSET
    )

    print("[1/6] 插入用户数据...")
    await seed_users(conn)
    await conn.commit()

    print("[2/6] 插入路由规则...")
    await seed_routing_rules(conn)
    await conn.commit()

    print("[3/6] 插入升级规则...")
    await seed_escalation_rules(conn)
    await conn.commit()

    print("[4/6] 插入SOP知识库...")
    await seed_sop_knowledge(conn)
    await conn.commit()

    print("[5/6] 插入质保记录...")
    await seed_warranty_records(conn)
    await conn.commit()

    print("[6/6] 插入出单映射规则...")
    await seed_order_mapping_rules(conn)
    await conn.commit()

    conn.close()
    print()
    print("种子数据插入完成！")
    print()
    print("默认账号：")
    print("  admin     / admin123  (管理员)")
    print("  zhangsan  / staff123  (一线员工)")
    print("  lisi      / manager123 (部门经理)")
    print("  wangwu    / gm123     (总经理)")


if __name__ == "__main__":
    asyncio.run(main())
