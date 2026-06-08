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

    def register(self, username, password, role="frontline_staff"):
        try:
            url = f"{self.base_url}/auth/register"
            payload = {"username": username, "password": password, "role": role}
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None
