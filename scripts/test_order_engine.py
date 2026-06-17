"""测试出单引擎 - 提交客诉验证Step5自动出单"""
import requests
import json

BASE = "http://localhost:8000"

# 登录
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
token = r.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

print("=" * 60)
print("测试出单引擎 - 提交客诉验证Step5自动出单")
print("=" * 60)

# 提交一条测试客诉（配件缺失 - 应触发补发单）
complaint_data = {
    "customer_name": "测试客户",
    "customer_phone": "13800138000",
    "text": "我购买的Pro-Max-V2设备，批次B2026-03，收货后发现缺少电源适配器和数据线，急需补发。订单号：DD20260615001"
}

r = requests.post(f"{BASE}/api/v1/customer/submit", data=complaint_data)
print(f"\n提交客诉: {r.status_code}")
result = r.json()
print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)[:1000]}")

# 检查出单结果
order_result = result.get("data", {}).get("order_result")
if order_result:
    print(f"\n出单结果:")
    if isinstance(order_result, list):
        # customer.py 返回的是出单列表
        print(f"  出单数量: {len(order_result)}")
        for o in order_result:
            print(f"  - 单号: {o.get('order_no')}")
            print(f"    类型: {o.get('order_type_label')}")
            print(f"    部门: {o.get('department')}")
            print(f"    SLA: {o.get('sla_hours')}h")
    elif isinstance(order_result, dict):
        print(f"  成功: {order_result.get('success')}")
        print(f"  出单状态: {order_result.get('order_status')}")
        orders = order_result.get("orders", [])
        print(f"  出单数量: {len(orders)}")
        for o in orders:
            print(f"  - 单号: {o.get('order_no')}")
            print(f"    类型: {o.get('order_type_label')}")
            print(f"    部门: {o.get('department')}")
            print(f"    SLA: {o.get('sla_hours')}h")
else:
    print("\n未触发出单引擎")

# 查询出单列表验证
r = requests.get(f"{BASE}/api/v1/orders", headers=headers)
data = r.json()
print(f"\n出单列表查询: {r.status_code}, 总数: {data.get('total', 0)}")
if data.get("data"):
    for o in data["data"][:3]:
        print(f"  - {o.get('order_no')} | {o.get('order_type_label')} | {o.get('status')} | {o.get('department')}")

print("\n" + "=" * 60)
print("测试完成!")
