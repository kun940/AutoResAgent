import os

import requests


class ApiClient:
    def __init__(self, base_url="http://localhost:8000/api/v1"):
        self.base_url = base_url.rstrip("/")
        self.timeout = 10
        self.token = None
        self.user_info = None

    def submit_complaint(self, text, image_paths=None, customer_name=None, customer_phone=None):
        try:
            url = f"{self.base_url}/complaints/submit"
            data = {"text": text}
            if customer_name:
                data["customer_name"] = customer_name
            if customer_phone:
                data["customer_phone"] = customer_phone
            files = []
            if image_paths:
                for path in image_paths:
                    if os.path.isfile(path):
                        filename = os.path.basename(path)
                        files.append(("images", (filename, open(path, "rb"), "application/octet-stream")))
            try:
                resp = requests.post(url, data=data, files=files, timeout=120)
                resp.raise_for_status()
                return resp.json()
            finally:
                for _, file_tuple in files:
                    file_tuple[1].close()
        except Exception:
            return None

    def get_tickets(self, status=None, urgency_level=None, target_role=None, page=1, page_size=20):
        try:
            url = f"{self.base_url}/tickets"
            params = {"page": page, "page_size": page_size}
            if status:
                params["status"] = status
            if urgency_level:
                params["urgency_level"] = urgency_level
            if target_role:
                params["target_role"] = target_role
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_ticket(self, ticket_id):
        try:
            url = f"{self.base_url}/tickets/{ticket_id}"
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def update_ticket_status(self, ticket_id, status, note=None):
        try:
            url = f"{self.base_url}/tickets/{ticket_id}/status"
            payload = {"status": status}
            if note:
                payload["note"] = note
            resp = requests.put(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def escalate_ticket(self, ticket_id, to_level, reason):
        try:
            url = f"{self.base_url}/tickets/{ticket_id}/escalate"
            payload = {"to_level": to_level, "reason": reason}
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def reassign_ticket(self, ticket_id, target_username, target_role, reason):
        try:
            url = f"{self.base_url}/tickets/{ticket_id}/reassign"
            payload = {"target_username": target_username, "target_role": target_role, "reason": reason}
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_dashboard_stats(self, target_role=None):
        try:
            url = f"{self.base_url}/dashboard/stats"
            params = {}
            if target_role:
                params["target_role"] = target_role
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_subordinate_overview(self, role):
        try:
            url = f"{self.base_url}/dashboard/subordinate-overview"
            params = {"role": role}
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_unread_notification_count(self):
        try:
            url = f"{self.base_url}/notifications/unread-count"
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def check_health(self):
        try:
            url = self.base_url.rsplit("/api", 1)[0] + "/health"
            resp = requests.get(url, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def login(self, username, password):
        try:
            url = f"{self.base_url}/auth/login"
            payload = {"username": username, "password": password}
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_dashboard_quality(self, target_role=None):
        """获取看板出单质量统计数据"""
        try:
            url = f"{self.base_url}/dashboard/quality"
            params = {}
            if target_role:
                params["target_role"] = target_role
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_new_tickets_count(self, since=None):
        """获取新工单数量（用于轮询通知）"""
        try:
            url = f"{self.base_url}/tickets"
            params = {"page": 1, "page_size": 1}
            if since:
                params["since"] = since
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def register(self, username, password, role="frontline_staff"):
        try:
            url = f"{self.base_url}/auth/register"
            payload = {"username": username, "password": password, "role": role}
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    # ===== 出单管理 =====

    def get_orders(self, order_type=None, status=None, ticket_id=None, department=None, page=1, page_size=20):
        """查询单据列表"""
        try:
            url = f"{self.base_url}/orders"
            params = {"page": page, "page_size": page_size}
            if order_type:
                params["order_type"] = order_type
            if status:
                params["status"] = status
            if ticket_id:
                params["ticket_id"] = ticket_id
            if department:
                params["department"] = department
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_order(self, order_id):
        """查询单据详情"""
        try:
            url = f"{self.base_url}/orders/{order_id}"
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def update_order_status(self, order_id, status, note=None):
        """更新单据状态"""
        try:
            url = f"{self.base_url}/orders/{order_id}/status"
            payload = {"status": status}
            if note:
                payload["note"] = note
            resp = requests.put(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_orders_by_ticket(self, ticket_id):
        """根据工单ID查询关联单据"""
        try:
            url = f"{self.base_url}/orders/by-ticket/{ticket_id}"
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def create_order(self, ticket_id, order_type, department=None, sla_hours=48, material_list=None, remark=None):
        """手动创建出单"""
        try:
            url = f"{self.base_url}/orders"
            payload = {"ticket_id": ticket_id, "order_type": order_type}
            if department:
                payload["department"] = department
            if sla_hours:
                payload["sla_hours"] = sla_hours
            if material_list:
                payload["material_list"] = material_list
            if remark:
                payload["remark"] = remark
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    # ===== 质量追溯 =====

    def get_quality_trace(self, model_number=None, batch_code=None, start_date=None, end_date=None, group_by="model", page=1, page_size=20):
        """质量追溯查询"""
        try:
            url = f"{self.base_url}/quality/trace"
            params = {"group_by": group_by, "page": page, "page_size": page_size}
            if model_number:
                params["model_number"] = model_number
            if batch_code:
                params["batch_code"] = batch_code
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_quality_dashboard(self, start_date=None, end_date=None, model_number=None):
        """质量分析看板数据"""
        try:
            url = f"{self.base_url}/quality/dashboard"
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            if model_number:
                params["model_number"] = model_number
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def export_quality_report(self, format="xlsx", model_number=None, batch_code=None, start_date=None, end_date=None):
        """导出质量报表"""
        try:
            url = f"{self.base_url}/quality/export"
            params = {"format": format}
            if model_number:
                params["model_number"] = model_number
            if batch_code:
                params["batch_code"] = batch_code
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    # ===== 映射规则 =====

    def get_mapping_rules(self, is_active=None, issue_category=None):
        """查询映射规则"""
        try:
            url = f"{self.base_url}/orders/mapping-rules"
            params = {}
            if is_active is not None:
                params["is_active"] = is_active
            if issue_category:
                params["issue_category"] = issue_category
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def create_mapping_rule(self, issue_category, urgency_level, order_type, department, sla_hours=48, priority=0, description=None):
        """创建映射规则"""
        try:
            url = f"{self.base_url}/orders/mapping-rules"
            payload = {
                "issue_category": issue_category,
                "urgency_level": urgency_level,
                "order_type": order_type,
                "department": department,
                "sla_hours": sla_hours,
                "priority": priority,
            }
            if description:
                payload["description"] = description
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def update_mapping_rule(self, rule_id, **kwargs):
        """更新映射规则"""
        try:
            url = f"{self.base_url}/orders/mapping-rules/{rule_id}"
            resp = requests.put(url, json=kwargs, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def delete_mapping_rule(self, rule_id):
        """删除映射规则"""
        try:
            url = f"{self.base_url}/orders/mapping-rules/{rule_id}"
            resp = requests.delete(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    # ===== 批量操作 =====

    def batch_reassign(self, ticket_ids, target_username, target_role, reason=None):
        """批量转派"""
        try:
            url = f"{self.base_url}/tickets/batch/reassign"
            payload = {
                "ticket_ids": ticket_ids,
                "target_username": target_username,
                "target_role": target_role,
                "reason": reason or "",
            }
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def batch_escalate(self, ticket_ids, reason=None):
        """批量升级"""
        try:
            url = f"{self.base_url}/tickets/batch/escalate"
            payload = {
                "ticket_ids": ticket_ids,
                "reason": reason or "",
            }
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def batch_close(self, ticket_ids, reason=None):
        """批量关闭"""
        try:
            url = f"{self.base_url}/tickets/batch/close"
            payload = {
                "ticket_ids": ticket_ids,
                "reason": reason or "",
            }
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    # ===== 搜索和导出 =====

    def search_tickets(self, keyword, status=None, urgency_level=None, page=1, page_size=20):
        """关键词搜索工单"""
        try:
            url = f"{self.base_url}/tickets/search"
            params = {"keyword": keyword, "page": page, "page_size": page_size}
            if status:
                params["status"] = status
            if urgency_level:
                params["urgency_level"] = urgency_level
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def export_tickets(self, format="xlsx", status=None, urgency_level=None, start_date=None, end_date=None):
        """导出工单数据，返回 (bytes, content_type, filename) 或 None"""
        try:
            url = f"{self.base_url}/tickets/export"
            params = {"format": format}
            if status:
                params["status"] = status
            if urgency_level:
                params["urgency_level"] = urgency_level
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            cd = resp.headers.get("Content-Disposition", "")
            filename = "tickets_export.xlsx" if format == "xlsx" else "tickets_export.csv"
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('" ')
            return resp.content, content_type, filename
        except Exception:
            return None
