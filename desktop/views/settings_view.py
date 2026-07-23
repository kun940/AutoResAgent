import os
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QGroupBox, QFormLayout, QCheckBox,
    QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from desktop.api_client import ApiClient


CONFIG_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


class HealthCheckThread(QThread):
    result_ready = pyqtSignal(bool)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client

    def run(self):
        is_healthy = self.api_client.check_health()
        self.result_ready.emit(is_healthy)


class SettingsView(QWidget):
    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._setup_ui()
        self._load_local_config()
        self._test_connection()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        title = QLabel("系统设置")
        title.setObjectName("page_title")
        main_layout.addWidget(title)

        self._build_connection_group(main_layout)
        self._build_notification_group(main_layout)
        self._build_about_group(main_layout)
        main_layout.addStretch()

    def _build_connection_group(self, parent_layout):
        group = QGroupBox("后端连接状态")
        form = QFormLayout(group)
        form.setSpacing(12)

        self.url_label = QLabel(self.api_client.base_url)
        self.url_label.setStyleSheet("color: #1E2329; font-weight: 600;")
        form.addRow("后端地址：", self.url_label)

        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #BDC3C7; font-size: 16px;")
        status_row.addWidget(self.status_dot)

        self.status_text = QLabel("检测中...")
        self.status_text.setStyleSheet("color: #8A94A6; font-size: 13px;")
        status_row.addWidget(self.status_text)
        status_row.addStretch()

        self.test_btn = QPushButton("测试连接")
        self.test_btn.setFixedWidth(100)
        self.test_btn.clicked.connect(self._test_connection)
        status_row.addWidget(self.test_btn)

        form.addRow("连接状态：", status_row)
        parent_layout.addWidget(group)

    def _build_notification_group(self, parent_layout):
        group = QGroupBox("通知设置")
        form = QFormLayout(group)
        form.setSpacing(12)

        self.chk_new_ticket = QCheckBox("启用新工单通知")
        self.chk_new_ticket.setChecked(True)
        form.addRow("", self.chk_new_ticket)

        self.chk_sla_warning = QCheckBox("启用SLA预警通知")
        self.chk_sla_warning.setChecked(True)
        form.addRow("", self.chk_sla_warning)

        self.chk_escalation = QCheckBox("启用升级通知")
        self.chk_escalation.setChecked(True)
        form.addRow("", self.chk_escalation)

        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(10, 120)
        self.poll_spin.setSingleStep(10)
        self.poll_spin.setValue(30)
        self.poll_spin.setSuffix(" 秒")
        form.addRow("轮询间隔：", self.poll_spin)

        self.save_notify_btn = QPushButton("保存通知设置")
        self.save_notify_btn.setFixedWidth(120)
        self.save_notify_btn.clicked.connect(self._save_local_config)
        form.addRow("", self.save_notify_btn)

        parent_layout.addWidget(group)

    def _build_about_group(self, parent_layout):
        group = QGroupBox("关于")
        form = QFormLayout(group)
        form.setSpacing(8)

        form.addRow("系统名称：", QLabel("客诉自动回复出单智能体 v1.0.0"))
        form.addRow("技术栈：", QLabel("PyQt6 + FastAPI + LangChain + DeepSeek + Qwen + ChromaDB"))
        form.addRow("版权信息：", QLabel("© 2026"))

        parent_layout.addWidget(group)

    def _test_connection(self):
        self.status_dot.setStyleSheet("color: #BDC3C7; font-size: 16px;")
        self.status_text.setText("检测中...")
        self.status_text.setStyleSheet("color: #7F8C8D; font-size: 13px;")
        self.test_btn.setEnabled(False)

        self._health_thread = HealthCheckThread(self.api_client)
        self._health_thread.result_ready.connect(self._on_health_result)
        self._health_thread.start()

    def _on_health_result(self, is_healthy):
        self.test_btn.setEnabled(True)
        if is_healthy:
            self.status_dot.setStyleSheet("color: #3A7D5F; font-size: 16px;")
            self.status_text.setText("已连接")
            self.status_text.setStyleSheet("color: #3A7D5F; font-size: 13px; font-weight: 600;")
        else:
            self.status_dot.setStyleSheet("color: #A8423A; font-size: 16px;")
            self.status_text.setText("未连接")
            self.status_text.setStyleSheet("color: #A8423A; font-size: 13px; font-weight: 600;")

    def _load_local_config(self):
        try:
            if os.path.isfile(CONFIG_JSON_PATH):
                with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)

                notifications = config.get("notifications", {})
                self.chk_new_ticket.setChecked(notifications.get("new_ticket", True))
                self.chk_sla_warning.setChecked(notifications.get("sla_warning", True))
                self.chk_escalation.setChecked(notifications.get("escalation", True))
                self.poll_spin.setValue(config.get("poll_interval_seconds", 30))
        except Exception:
            pass

    def _save_local_config(self):
        try:
            config = {
                "notifications": {
                    "new_ticket": self.chk_new_ticket.isChecked(),
                    "sla_warning": self.chk_sla_warning.isChecked(),
                    "escalation": self.chk_escalation.isChecked(),
                },
                "poll_interval_seconds": self.poll_spin.value(),
            }

            os.makedirs(os.path.dirname(CONFIG_JSON_PATH), exist_ok=True)
            with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            QMessageBox.information(self, "保存成功", "通知设置已保存")

        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存通知设置时出错：{str(e)}")
