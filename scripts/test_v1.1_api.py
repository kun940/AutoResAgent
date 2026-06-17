"""v1.1 API 接口验证脚本"""
import requests
import json

BASE = "http://localhost:8000"

# 登录
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
token = r.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

print("=" * 60)
print("v1.1 API 接口验证")
print("=" * 60)

# 1. 出单列表
r = requests.get(f"{BASE}/api/v1/orders", headers=headers)
print(f"\n[1] 出单列表: {r.status_code}")
print(f"    响应: {json.dumps(r.json(), ensure_ascii=False)[:200]}")

# 2. 映射规则
r = requests.get(f"{BASE}/api/v1/orders/mapping-rules", headers=headers)
data = r.json()
rule_count = len(data.get("data", [])) if r.status_code == 200 else 0
print(f"\n[2] 映射规则: {r.status_code}, {rule_count} 条规则")

# 3. 质量看板
r = requests.get(f"{BASE}/api/v1/quality/dashboard", headers=headers)
data = r.json()
overview = data.get("data", {}).get("overview", {}) if r.status_code == 200 else {}
print(f"\n[3] 质量看板: {r.status_code}")
print(f"    概览: {json.dumps(overview, ensure_ascii=False)}")

# 4. 质量追溯
r = requests.get(f"{BASE}/api/v1/quality/trace", headers=headers)
data = r.json()
summary = data.get("data", {}).get("summary", {}) if r.status_code == 200 else {}
print(f"\n[4] 质量追溯: {r.status_code}")
print(f"    汇总: {json.dumps(summary, ensure_ascii=False)}")

# 5. 工单搜索
r = requests.get(f"{BASE}/api/v1/tickets/search?keyword=Pro", headers=headers)
data = r.json()
search_data = data.get("data", [])
if isinstance(search_data, list):
    total = len(search_data)
elif isinstance(search_data, dict):
    total = search_data.get("total", 0)
else:
    total = 0
print(f"\n[5] 工单搜索: {r.status_code}, 找到 {total} 条")

# 6. 工单导出
r = requests.get(f"{BASE}/api/v1/tickets/export?format=csv", headers=headers)
print(f"\n[6] 工单导出(CSV): {r.status_code}, {len(r.content)} bytes")

# 7. 质量报表导出
r = requests.get(f"{BASE}/api/v1/quality/export?format=csv", headers=headers)
print(f"\n[7] 质量报表导出(CSV): {r.status_code}, {len(r.content)} bytes")

print("\n" + "=" * 60)
print("验证完成!")
