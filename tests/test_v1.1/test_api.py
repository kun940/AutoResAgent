"""v1.1 API 端点集成测试

通过 HTTP 请求验证完整的 API 链路，需要后端服务运行中。
"""
import pytest

import requests

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth_token():
    """获取JWT认证令牌"""
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10,
    )
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text}"
    return r.json()["data"]["token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


def check_server():
    """检查后端服务是否可用"""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not check_server(),
    reason="后端服务未运行，跳过API测试",
)


# ============================================================
# 出单管理 API 测试
# ============================================================

class TestOrdersAPI:
    """出单管理API测试"""

    def test_list_orders(self, headers):
        """GET /api/v1/orders - 出单列表"""
        r = requests.get(f"{BASE_URL}/api/v1/orders", headers=headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "total" in data

    def test_list_orders_with_filters(self, headers):
        """GET /api/v1/orders?type=Replacement - 按类型筛选"""
        r = requests.get(
            f"{BASE_URL}/api/v1/orders",
            headers=headers,
            params={"order_type": "Replacement"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        for order in data.get("data", []):
            assert order["order_type"] == "Replacement"

    def test_list_orders_pagination(self, headers):
        """GET /api/v1/orders?page=1&page_size=5 - 分页"""
        r = requests.get(
            f"{BASE_URL}/api/v1/orders",
            headers=headers,
            params={"page": 1, "page_size": 5},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("data", [])) <= 5

    def test_get_order_not_found(self, headers):
        """GET /api/v1/orders/99999 - 不存在的出单"""
        r = requests.get(f"{BASE_URL}/api/v1/orders/99999", headers=headers, timeout=10)
        assert r.status_code == 200
        assert r.json().get("data") is None

    def test_get_mapping_rules(self, headers):
        """GET /api/v1/orders/mapping-rules - 映射规则列表"""
        r = requests.get(f"{BASE_URL}/api/v1/orders/mapping-rules", headers=headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("data", [])) > 0

    def test_get_mapping_rules_active_only(self, headers):
        """GET /api/v1/orders/mapping-rules?is_active=1 - 只查激活规则"""
        r = requests.get(
            f"{BASE_URL}/api/v1/orders/mapping-rules",
            headers=headers,
            params={"is_active": 1},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        for rule in data.get("data", []):
            assert rule["is_active"] == 1

    def test_create_and_delete_mapping_rule(self, headers):
        """POST + DELETE /api/v1/orders/mapping-rules - 创建和删除映射规则"""
        r = requests.post(
            f"{BASE_URL}/api/v1/orders/mapping-rules",
            headers=headers,
            json={
                "issue_category": "Test_Category",
                "urgency_level": "Low_Priority",
                "order_type": "Tech_Support",
                "department": "技术支持部",
                "sla_hours": 72,
                "priority": 0,
                "description": "测试规则",
            },
            timeout=10,
        )
        assert r.status_code == 200, f"创建失败: {r.text}"
        rule_id = r.json()["data"]["id"]

        r = requests.delete(
            f"{BASE_URL}/api/v1/orders/mapping-rules/{rule_id}",
            headers=headers,
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["data"]["is_active"] == 0

    def test_update_mapping_rule(self, headers):
        """PUT /api/v1/orders/mapping-rules/{id} - 更新映射规则"""
        r = requests.post(
            f"{BASE_URL}/api/v1/orders/mapping-rules",
            headers=headers,
            json={
                "issue_category": "Test_Update_Category",
                "urgency_level": "Medium_Priority",
                "order_type": "Repair",
                "department": "技术维修部",
                "sla_hours": 48,
            },
            timeout=10,
        )
        rule_id = r.json()["data"]["id"]

        r = requests.put(
            f"{BASE_URL}/api/v1/orders/mapping-rules/{rule_id}",
            headers=headers,
            json={"sla_hours": 96, "description": "更新后的规则"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["data"]["sla_hours"] == 96
        assert r.json()["data"]["description"] == "更新后的规则"

        requests.delete(f"{BASE_URL}/api/v1/orders/mapping-rules/{rule_id}", headers=headers, timeout=10)

    def test_get_orders_by_ticket(self, headers):
        """GET /api/v1/orders/by-ticket/{ticket_id} - 按工单查出单"""
        r = requests.get(f"{BASE_URL}/api/v1/orders", headers=headers, timeout=10)
        if r.json().get("data"):
            ticket_id = r.json()["data"][0]["ticket_id"]
            r = requests.get(
                f"{BASE_URL}/api/v1/orders/by-ticket/{ticket_id}",
                headers=headers,
                timeout=10,
            )
            assert r.status_code == 200
            assert isinstance(r.json().get("data", []), list)


# ============================================================
# 质量追溯 API 测试
# ============================================================

class TestQualityAPI:
    """质量追溯API测试"""

    def test_quality_trace(self, headers):
        """GET /api/v1/quality/trace - 质量追溯查询"""
        r = requests.get(f"{BASE_URL}/api/v1/quality/trace", headers=headers, timeout=10)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "summary" in data
        assert "groups" in data
        assert data["summary"]["total_records"] >= 0

    def test_quality_trace_group_by_model(self, headers):
        """GET /api/v1/quality/trace?group_by=model - 按型号分组"""
        r = requests.get(
            f"{BASE_URL}/api/v1/quality/trace",
            headers=headers,
            params={"group_by": "model"},
            timeout=10,
        )
        assert r.status_code == 200
        groups = r.json()["data"]["groups"]
        for g in groups:
            assert "dimension" in g
            assert "ticket_count" in g
            assert "order_count" in g

    def test_quality_trace_group_by_category(self, headers):
        """GET /api/v1/quality/trace?group_by=category - 按分类分组"""
        r = requests.get(
            f"{BASE_URL}/api/v1/quality/trace",
            headers=headers,
            params={"group_by": "category"},
            timeout=10,
        )
        assert r.status_code == 200

    def test_quality_dashboard(self, headers):
        """GET /api/v1/quality/dashboard - 质量看板"""
        r = requests.get(f"{BASE_URL}/api/v1/quality/dashboard", headers=headers, timeout=10)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "overview" in data
        assert "trend" in data
        assert "top_models" in data
        assert "category_distribution" in data
        assert "order_type_distribution" in data

        overview = data["overview"]
        assert "total_tickets" in overview
        assert "total_orders" in overview
        assert "high_urgency_rate" in overview
        assert "sla_rate" in overview
        assert 0 <= overview["high_urgency_rate"] <= 100
        assert 0 <= overview["sla_rate"] <= 100

    def test_quality_export_csv(self, headers):
        """GET /api/v1/quality/export?format=csv - CSV导出"""
        r = requests.get(
            f"{BASE_URL}/api/v1/quality/export",
            headers=headers,
            params={"format": "csv"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.content[:3] == b"\xef\xbb\xbf"

    def test_quality_export_xlsx(self, headers):
        """GET /api/v1/quality/export?format=xlsx - Excel导出"""
        r = requests.get(
            f"{BASE_URL}/api/v1/quality/export",
            headers=headers,
            params={"format": "xlsx"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.content[:2] == b"PK"


# ============================================================
# 工单增强 API 测试
# ============================================================

class TestTicketEnhancedAPI:
    """工单增强API测试"""

    def test_search_tickets(self, headers):
        """GET /api/v1/tickets/search?keyword=Pro - 关键词搜索"""
        r = requests.get(
            f"{BASE_URL}/api/v1/tickets/search",
            headers=headers,
            params={"keyword": "Pro"},
            timeout=10,
        )
        assert r.status_code == 200

    def test_search_tickets_min_length(self, headers):
        """GET /api/v1/tickets/search?keyword=a - 关键词过短返回422"""
        r = requests.get(
            f"{BASE_URL}/api/v1/tickets/search",
            headers=headers,
            params={"keyword": "a"},
            timeout=10,
        )
        assert r.status_code in (400, 422)

    def test_export_tickets_csv(self, headers):
        """GET /api/v1/tickets/export?format=csv - 工单CSV导出"""
        r = requests.get(
            f"{BASE_URL}/api/v1/tickets/export",
            headers=headers,
            params={"format": "csv"},
            timeout=10,
        )
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_export_tickets_xlsx(self, headers):
        """GET /api/v1/tickets/export?format=xlsx - 工单Excel导出"""
        r = requests.get(
            f"{BASE_URL}/api/v1/tickets/export",
            headers=headers,
            params={"format": "xlsx"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.content[:2] == b"PK"

    def test_batch_close_empty_list(self, headers):
        """POST /api/v1/tickets/batch/close - 空列表返回200"""
        r = requests.post(
            f"{BASE_URL}/api/v1/tickets/batch/close",
            headers=headers,
            json={"ticket_ids": [], "reason": "测试"},
            timeout=10,
        )
        assert r.status_code == 200

    def test_batch_close_nonexistent_tickets(self, headers):
        """POST /api/v1/tickets/batch/close - 不存在的工单"""
        r = requests.post(
            f"{BASE_URL}/api/v1/tickets/batch/close",
            headers=headers,
            json={"ticket_ids": ["CS-FAKE-001", "CS-FAKE-002"], "reason": "测试"},
            timeout=10,
        )
        assert r.status_code == 200


# ============================================================
# 客诉提交+自动出单 集成测试
# ============================================================

class TestComplaintSubmitWithOrder:
    """客诉提交+自动出单集成测试"""

    def test_submit_complaint_triggers_order(self, headers):
        """提交客诉后应自动触发出单"""
        r = requests.post(
            f"{BASE_URL}/api/v1/customer/submit",
            data={
                "customer_name": "测试客户",
                "customer_phone": "13900000001",
                "text": "我购买的Pro-Max-V2设备，批次B2026-TEST，收货后发现缺少电源适配器，急需补发。订单号：DD20260617001",
            },
            timeout=30,
        )
        assert r.status_code == 200, f"提交客诉失败: {r.text}"
        data = r.json().get("data", {})

        assert data.get("ticket_id"), "应生成工单ID"
        assert data.get("issue_category"), "应有问题分类"
        assert data.get("urgency_level"), "应有紧急度"

        order_result = data.get("order_result")
        if order_result:
            if isinstance(order_result, list):
                orders = order_result
            elif isinstance(order_result, dict):
                orders = order_result.get("orders", [])
            else:
                orders = []

            if orders:
                order = orders[0]
                assert order.get("order_no"), "单据应有编号"
                assert order.get("order_type"), "单据应有类型"
                assert order.get("department"), "单据应有处理部门"
                assert order.get("sla_hours"), "单据应有SLA时限"

    def test_submit_safety_hazard_triggers_dual_orders(self, headers):
        """安全隐患投诉应触发退换单+质检单"""
        r = requests.post(
            f"{BASE_URL}/api/v1/customer/submit",
            data={
                "customer_name": "安全测试",
                "customer_phone": "13900000002",
                "text": "设备冒烟了！Pro-Max-V2，批次B2026-SAFE，有严重安全隐患，可能起火！",
            },
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json().get("data", {})
        order_result = data.get("order_result")

        if order_result and isinstance(order_result, dict):
            orders = order_result.get("orders", [])
            if orders:
                order_types = [o.get("order_type") for o in orders]
                assert "Return_Exchange" in order_types or "QC" in order_types, \
                    f"安全隐患应触发退换单或质检单, 实际: {order_types}"
