"""v1.2 API 端点集成测试

通过 HTTP 请求验证完整的 API 链路，需要后端服务运行中。
v1.2: 出单管理 API 已删除，质量追溯字段已更新。
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
            assert "archived_count" in g

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
        assert "action_type_distribution" in data

        overview = data["overview"]
        assert "total_tickets" in overview
        assert "total_archived" in overview
        assert "high_urgency_rate" in overview
        assert "archive_complete_rate" in overview
        assert 0 <= overview["high_urgency_rate"] <= 100
        assert 0 <= overview["archive_complete_rate"] <= 100

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
# 客诉提交+工单归档 集成测试
# ============================================================

class TestComplaintSubmitWithArchive:
    """客诉提交+工单归档集成测试（v1.2: 出单已移除，验证归档完整性）"""

    def test_submit_complaint_archives_ticket(self, headers):
        """提交客诉后应生成工单并完整归档"""
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
        assert data.get("auto_reply"), "应有自动回复内容"
        # v1.2: 不再返回 order_result
        assert "order_result" not in data, "v1.2 不应返回出单结果"

    def test_submit_safety_hazard_archived(self, headers):
        """安全隐患投诉应归档工单（v1.2: 不再触发出单）"""
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
        assert data.get("ticket_id"), "应生成工单ID"
        assert "order_result" not in data, "v1.2 不应返回出单结果"
