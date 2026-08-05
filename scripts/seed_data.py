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
        # --- 原有6条（补充 emergency_actions 和 scenario_tags） ---
        ("Missing_Parts", "配件缺失补发流程",
         "1. 确认缺失配件名称和数量\n2. 核对订单明细\n3. 安排补发物流\n4. 预计3-5个工作日送达\n5. 补发后短信通知客户",
         "Low_Priority", '["缺件", "缺失", "少件", "螺丝", "配件"]',
         '["确认缺失配件名称", "核对订单明细"]',
         '["配件缺失", "少件"]'),
        ("Hardware_Thermal_Runaway", "设备过热/冒烟紧急处置",
         "1. 立即切断设备总电源\n2. 人员远离设备，保持通风\n3. 严禁用水灭火\n4. 拨打售后紧急热线400-XXX-XXXX\n5. 等待技术人员到场处理",
         "High_Priority", '["冒烟", "过热", "烧焦", "发热", "起火"]',
         '["立即切断设备总电源", "人员远离设备保持通风", "严禁用水灭火", "拨打售后紧急热线400-XXX-XXXX"]',
         '["冒烟", "过热", "烧焦", "起火"]'),
        ("Electrical_Leakage", "漏电紧急处置SOP",
         "1. 立即切断总闸并远离设备\n2. 确保人员安全撤离\n3. 拨打售后紧急热线\n4. 严禁触碰设备任何部位",
         "High_Priority", '["漏电", "触电", "带电", "麻手"]',
         '["立即切断总闸", "人员远离设备", "严禁触碰设备任何部位", "拨打售后紧急热线400-XXX-XXXX"]',
         '["漏电", "触电", "带电", "麻手"]'),
        ("Hardware_Malfunction", "设备频繁重启排查指引",
         "1. 检查电源连接是否稳定\n2. 确认使用环境温度是否过高\n3. 记录重启频率和时间段\n4. 联系技术支持安排远程诊断",
         "Medium_Priority", '["重启", "死机", "蓝屏", "卡顿", "频繁"]',
         '["检查电源连接是否稳定", "确认使用环境温度"]',
         '["重启", "死机", "频繁重启"]'),
        ("Software_Bug", "软件崩溃恢复操作",
         "1. 记录崩溃前的操作步骤和错误信息\n2. 尝试重启软件并检查更新\n3. 清除缓存和临时文件\n4. 如问题持续，联系技术支持远程诊断\n5. 必要时提供软件重装包",
         "Medium_Priority", '["崩溃", "软件", "闪退", "报错", "程序"]',
         '["尝试重启软件并检查更新", "清除缓存和临时文件"]',
         '["软件崩溃", "闪退", "报错"]'),
        ("Batch_Defect", "疑似批次缺陷上报流程",
         "1. 记录产品批次号\n2. 收集同批次其他客户反馈\n3. 上报技术质量部\n4. 启动批次追溯程序\n5. 48小时内给出初步结论",
         "Medium_Priority", '["批次", "批量", "同一批", "多台"]',
         '["记录产品批次号", "上报技术质量部"]',
         '["批次缺陷", "批量故障"]'),
        # --- 新增12条 ---
        ("Hardware_Thermal_Runaway", "设备起火紧急处置SOP",
         "1. 立即切断设备总电源/总闸\n2. 人员立即远离设备，保持至少3米安全距离\n3. 严禁用水灭火，使用干粉灭火器或CO2灭火器\n4. 拨打119火警电话（如火势不可控）\n5. 拨打售后紧急热线400-XXX-XXXX\n6. 等待消防和技术人员到场处理",
         "High_Priority", '["起火", "明火", "燃烧", "火焰", "着火"]',
         '["立即切断设备总电源/总闸", "人员立即远离设备保持至少3米安全距离", "严禁用水灭火", "拨打119火警电话", "拨打售后紧急热线400-XXX-XXXX"]',
         '["起火", "明火", "燃烧"]'),
        ("Electrical_Leakage", "触电事故紧急处置SOP",
         "1. 立即切断总闸/总电源（切勿直接触碰触电者）\n2. 使用绝缘物体（干燥木棍/橡胶手套）将触电者与电源分离\n3. 如触电者失去意识，立即拨打120急救电话\n4. 拨打售后紧急热线400-XXX-XXXX\n5. 保护现场，等待专业人员到场",
         "High_Priority", '["触电", "电击", "人员受伤", "电伤"]',
         '["立即切断总闸/总电源", "使用绝缘物体将触电者与电源分离", "如失去意识立即拨打120", "拨打售后紧急热线400-XXX-XXXX"]',
         '["触电", "电击", "人员受伤"]'),
        ("Hardware_Thermal_Runaway", "设备异响/异味排查处置",
         "1. 立即切断设备总电源\n2. 人员远离设备，保持通风\n3. 严禁继续使用设备\n4. 记录异响/异味出现的时间和特征\n5. 拨打售后紧急热线400-XXX-XXXX\n6. 等待技术人员到场检测",
         "High_Priority", '["异响", "异味", "烧焦味", "嗡嗡声", "刺耳"]',
         '["立即切断设备总电源", "人员远离设备保持通风", "严禁继续使用设备", "拨打售后紧急热线400-XXX-XXXX"]',
         '["异响", "异味", "烧焦味"]'),
        ("Hardware_Malfunction", "设备无法启动排查指引",
         "1. 检查电源线是否插紧、电源开关是否打开\n2. 确认电源插座有电（尝试更换插座）\n3. 检查保险丝/断路器是否跳闸\n4. 记录启动时的指示灯状态和报警信息\n5. 联系技术支持安排远程诊断或上门维修",
         "Medium_Priority", '["无法启动", "开不了机", "不通电", "没反应", "启动失败"]',
         '["检查电源线是否插紧", "确认电源插座有电", "检查保险丝/断路器"]',
         '["无法启动", "开不了机", "不通电"]'),
        ("Hardware_Malfunction", "设备显示屏故障处置",
         "1. 检查显示屏连接线是否松动\n2. 尝试重启设备观察是否恢复\n3. 记录显示屏故障现象（黑屏/花屏/闪烁）\n4. 如有外接显示器接口，尝试外接显示器确认主机状态\n5. 联系技术支持安排维修",
         "Medium_Priority", '["黑屏", "花屏", "闪烁", "显示异常", "屏幕"]',
         '["检查显示屏连接线是否松动", "尝试重启设备观察是否恢复"]',
         '["黑屏", "花屏", "显示异常"]'),
        ("Software_Bug", "系统死机/卡顿恢复操作",
         "1. 等待30秒观察是否自动恢复\n2. 尝试按Ctrl+Alt+Delete或设备复位键强制重启\n3. 重启后检查系统日志和错误报告\n4. 关闭不必要的后台程序\n5. 检查系统更新和磁盘空间\n6. 如问题持续，联系技术支持",
         "Medium_Priority", '["死机", "卡顿", "无响应", "卡死", "冻结"]',
         '["等待30秒观察是否自动恢复", "尝试强制重启", "检查系统日志"]',
         '["死机", "卡顿", "无响应"]'),
        ("Missing_Parts", "配件缺失加急补发流程",
         "1. 确认缺失配件名称、型号和数量\n2. 核对订单明细和发货清单\n3. 加急安排补发物流（优先顺丰/京东）\n4. 预计1-2个工作日送达\n5. 补发后短信通知客户并跟踪签收",
         "Medium_Priority", '["缺件", "缺失", "少件", "加急", "紧急补发"]',
         '["确认缺失配件名称型号和数量", "加急安排补发物流"]',
         '["配件缺失", "加急补发"]'),
        ("Batch_Defect", "批次缺陷紧急召回流程",
         "1. 立即记录产品批次号和缺陷描述\n2. 上报技术质量部和总经理办公室\n3. 启动紧急批次追溯程序\n4. 通知同批次所有客户暂停使用\n5. 安排全批次召回和更换\n6. 24小时内给出处理方案",
         "High_Priority", '["批次缺陷", "批量故障", "召回", "紧急召回", "群体性"]',
         '["立即记录产品批次号和缺陷描述", "上报技术质量部和总经理办公室", "通知同批次所有客户暂停使用", "安排全批次召回和更换"]',
         '["批次缺陷", "紧急召回", "群体性风险"]'),
        ("Operation_Error", "设备操作失误指导SOP",
         "1. 确认客户具体操作步骤和遇到的问题\n2. 提供正确的操作流程指导\n3. 发送操作手册或视频教程链接\n4. 远程协助客户完成正确操作\n5. 如仍无法解决，安排技术支持跟进",
         "Low_Priority", '["不会用", "操作失误", "用错了", "不会操作", "操作不当"]',
         '["确认客户具体操作步骤", "提供正确的操作流程指导"]',
         '["操作失误", "不会用"]'),
        ("Hardware_Malfunction", "设备进水紧急处置SOP",
         "1. 立即切断设备总电源/总闸（切勿带电操作）\n2. 严禁尝试开机或使用设备\n3. 用干毛巾吸干表面水分\n4. 将设备放置在通风干燥处自然晾干\n5. 拨打售后紧急热线400-XXX-XXXX\n6. 等待技术人员到场检测",
         "High_Priority", '["进水", "水渍", "浸水", "淋雨", "漏水"]',
         '["立即切断设备总电源/总闸", "严禁尝试开机或使用设备", "用干毛巾吸干表面水分", "拨打售后紧急热线400-XXX-XXXX"]',
         '["进水", "水渍", "浸水"]'),
        ("Hardware_Malfunction", "设备异响排查指引",
         "1. 记录异响出现的时间、频率和特征\n2. 检查设备是否放置平稳\n3. 检查是否有异物进入设备内部\n4. 确认异响是否与特定操作相关\n5. 联系技术支持安排远程诊断或上门检测",
         "Medium_Priority", '["异响", "噪音", "嗡嗡声", "咔嗒声", "摩擦声"]',
         '["记录异响出现的时间频率和特征", "检查设备是否放置平稳"]',
         '["异响", "噪音"]'),
        ("Safety_Hazard", "安全隐患紧急上报处置",
         "1. 立即停止使用设备\n2. 人员远离设备并设置警示标识\n3. 拨打售后紧急热线400-XXX-XXXX\n4. 上报技术质量部和总经理办公室\n5. 保护现场，等待专业人员到场评估\n6. 24小时内给出安全隐患处置方案",
         "High_Priority", '["安全隐患", "危险", "受伤", "安全", "隐患"]',
         '["立即停止使用设备", "人员远离设备并设置警示标识", "拨打售后紧急热线400-XXX-XXXX", "上报技术质量部和总经理办公室"]',
         '["安全隐患", "危险", "受伤"]'),
        ("Other", "信息不完整补充采集流程",
         "1. 确认缺失的关键信息（订单号/型号/故障描述等）\n2. 向客户发送信息补充模板\n3. 引导客户提供缺失信息\n4. 信息补充完整后重新进入正常处理流程\n5. 超过48小时未补充，自动标记为待跟进",
         "Medium_Priority", '["信息不全", "缺少信息", "补充", "信息不完整", "缺订单号"]',
         '["确认缺失的关键信息", "向客户发送信息补充模板"]',
         '["信息不完整", "补充采集"]'),
    ]
    async with conn.cursor() as cur:
        for cat, title, content, urgency, keywords, emergency_actions, scenario_tags in sops:
            await cur.execute(
                "INSERT IGNORE INTO `sop_knowledge_base` (issue_category, title, content, urgency_level, keywords, emergency_actions, scenario_tags) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (cat, title, content, urgency, keywords, emergency_actions, scenario_tags)
            )
    print("  SOP知识: 18条")


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
