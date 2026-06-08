import os
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QGroupBox, QFormLayout, QCheckBox,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from desktop.api_client import ApiClient


PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ENV_PATH = os.path.join(PROJECT_ROOT, "config", ".env")
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
        self._deepseek_visible = False
        self._dashscope_visible = False
        self._deepseek_key = ""
        self._dashscope_key = ""
        self._setup_ui()
        self._load_env_config()
        self._load_local_config()
        self._test_connection()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        title = QLabel("系统设置")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2C3E50;")
        main_layout.addWidget(title)

        self._build_connection_group(main_layout)
        self._build_api_group(main_layout)
        self._build_notification_group(main_layout)
        self._build_about_group(main_layout)
        main_layout.addStretch()

    def _build_connection_group(self, parent_layout):
        group = QGroupBox("后端连接状态")
        form = QFormLayout(group)
        form.setSpacing(12)

        self.url_label = QLabel(self.api_client.base_url)
        self.url_label.setStyleSheet("color: #2C3E50; font-weight: bold;")
        form.addRow("后端地址：", self.url_label)

        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #BDC3C7; font-size: 16px;")
        status_row.addWidget(self.status_dot)

        self.status_text = QLabel("检测中...")
        self.status_text.setStyleSheet("color: #7F8C8D; font-size: 13px;")
        status_row.addWidget(self.status_text)
        status_row.addStretch()

        self.test_btn = QPushButton("测试连接")
        self.test_btn.setFixedWidth(100)
        self.test_btn.clicked.connect(self._test_connection)
        status_row.addWidget(self.test_btn)

        form.addRow("连接状态：", status_row)
        parent_layout.addWidget(group)

    def _build_api_group(self, parent_layout):
        group = QGroupBox("API配置")
        form = QFormLayout(group)
        form.setSpacing(12)

        deepseek_row = QHBoxLayout()
        self.deepseek_input = QLineEdit()
        self.deepseek_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepseek_input.setPlaceholderText("sk-****xxxx")
        deepseek_row.addWidget(self.deepseek_input, 1)

        self.deepseek_toggle = QPushButton("显示")
        self.deepseek_toggle.setFixedWidth(60)
        self.deepseek_toggle.clicked.connect(lambda: self._toggle_key_visibility("deepseek"))
        deepseek_row.addWidget(self.deepseek_toggle)
        form.addRow("DeepSeek API Key：", deepseek_row)

        dashscope_row = QHBoxLayout()
        self.dashscope_input = QLineEdit()
        self.dashscope_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.dashscope_input.setPlaceholderText("sk-****xxxx")
        dashscope_row.addWidget(self.dashscope_input, 1)

        self.dashscope_toggle = QPushButton("显示")
        self.dashscope_toggle.setFixedWidth(60)
        self.dashscope_toggle.clicked.connect(lambda: self._toggle_key_visibility("dashscope"))
        dashscope_row.addWidget(self.dashscope_toggle)
        form.addRow("DashScope API Key：", dashscope_row)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setSingleStep(10)
        self.timeout_spin.setSuffix(" 秒")
        form.addRow("LLM超时时间：", self.timeout_spin)

        self.save_api_btn = QPushButton("保存配置")
        self.save_api_btn.setFixedWidth(120)
        self.save_api_btn.clicked.connect(self._save_env_config)
        form.addRow("", self.save_api_btn)

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
            self.status_dot.setStyleSheet("color: #4CAF50; font-size: 16px;")
            self.status_text.setText("已连接")
            self.status_text.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
        else:
            self.status_dot.setStyleSheet("color: #FF4444; font-size: 16px;")
            self.status_text.setText("未连接")
            self.status_text.setStyleSheet("color: #FF4444; font-size: 13px; font-weight: bold;")

    def _toggle_key_visibility(self, key_name):
        if key_name == "deepseek":
            self._deepseek_visible = not self._deepseek_visible
            if self._deepseek_visible:
                self.deepseek_input.setEchoMode(QLineEdit.EchoMode.Normal)
                self.deepseek_toggle.setText("隐藏")
            else:
                self.deepseek_input.setEchoMode(QLineEdit.EchoMode.Password)
                self.deepseek_toggle.setText("显示")
        elif key_name == "dashscope":
            self._dashscope_visible = not self._dashscope_visible
            if self._dashscope_visible:
                self.dashscope_input.setEchoMode(QLineEdit.EchoMode.Normal)
                self.dashscope_toggle.setText("隐藏")
            else:
                self.dashscope_input.setEchoMode(QLineEdit.EchoMode.Password)
                self.dashscope_toggle.setText("显示")

    def _mask_key(self, key):
        if not key or len(key) < 8:
            return key
        return key[:3] + "****" + key[-4:]

    def _load_env_config(self):
        try:
            if not os.path.isfile(ENV_PATH):
                return
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

            env_dict = {}
            for line in lines:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    env_dict[key.strip()] = value.strip()

            self._deepseek_key = env_dict.get("DEEPSEEK_API_KEY", "")
            self._dashscope_key = env_dict.get("DASHSCOPE_API_KEY", "")

            self.deepseek_input.setText(self._deepseek_key)
            self.dashscope_input.setText(self._dashscope_key)

            timeout = env_dict.get("LLM_TIMEOUT_SECONDS", "60")
            try:
                self.timeout_spin.setValue(int(timeout))
            except ValueError:
                self.timeout_spin.setValue(60)

        except Exception:
            pass

    def _save_env_config(self):
        try:
            env_dict = {}
            if os.path.isfile(ENV_PATH):
                with open(ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            key, _, value = line.partition("=")
                            env_dict[key.strip()] = value.strip()

            new_deepseek = self.deepseek_input.text().strip()
            new_dashscope = self.dashscope_input.text().strip()
            new_timeout = str(self.timeout_spin.value())

            env_dict["DEEPSEEK_API_KEY"] = new_deepseek
            env_dict["DASHSCOPE_API_KEY"] = new_dashscope
            env_dict["LLM_TIMEOUT_SECONDS"] = new_timeout

            if os.path.isfile(ENV_PATH):
                with open(ENV_PATH, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                updated_keys = set()
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    if "=" in stripped and not stripped.startswith("#"):
                        key = stripped.split("=", 1)[0].strip()
                        if key in ("DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "LLM_TIMEOUT_SECONDS"):
                            new_lines.append(f"{key}={env_dict[key]}\n")
                            updated_keys.add(key)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                for key in ("DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "LLM_TIMEOUT_SECONDS"):
                    if key not in updated_keys:
                        new_lines.append(f"{key}={env_dict[key]}\n")

                with open(ENV_PATH, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            else:
                os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
                with open(ENV_PATH, "w", encoding="utf-8") as f:
                    f.write(f"DEEPSEEK_API_KEY={new_deepseek}\n")
                    f.write(f"DASHSCOPE_API_KEY={new_dashscope}\n")
                    f.write(f"LLM_TIMEOUT_SECONDS={new_timeout}\n")

            self._deepseek_key = new_deepseek
            self._dashscope_key = new_dashscope

            QMessageBox.information(self, "保存成功", "配置已保存，部分配置需重启后端生效")

        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存配置时出错：{str(e)}")

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
