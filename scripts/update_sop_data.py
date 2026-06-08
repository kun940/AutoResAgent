import asyncio
import aiomysql
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))


async def main():
    conn = await aiomysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        db=os.getenv("DB_NAME", "complaint_agent"),
    )
    cur = await conn.cursor()
    await cur.execute("DELETE FROM sop_knowledge_base")
    await conn.commit()
    print("Deleted all SOP records")

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
    for cat, title, content, urgency, keywords in sops:
        await cur.execute(
            "INSERT INTO sop_knowledge_base (issue_category, title, content, urgency_level, keywords) VALUES (%s, %s, %s, %s, %s)",
            (cat, title, content, urgency, keywords),
        )
    await conn.commit()

    await cur.execute("SELECT id, issue_category, title FROM sop_knowledge_base")
    rows = await cur.fetchall()
    for r in rows:
        print(r)

    conn.close()
    print("SOP data updated!")


if __name__ == "__main__":
    asyncio.run(main())
