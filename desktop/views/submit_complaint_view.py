from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFileDialog, QGroupBox, QFormLayout,
    QScrollArea, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from desktop.api_client import ApiClient


URGENCY_COLORS = {
    "High_Priority": "#FF4444",
    "Medium_Priority": "#FF9800",
    "Low_Priority": "#4CAF50",
}

URGENCY_LABELS = {
    "High_Priority": "高紧急",
    "Medium_Priority": "中紧急",
    "Low_Priority": "低紧急",
}


class SubmitThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, text, image_paths, customer_name, customer_phone):
        super().__init__()
        self.api_client = api_client
        self.text = text
        self.image_paths = image_paths
        self.customer_name = customer_name
        self.customer_phone = customer_phone

    def run(self):
        result = self.api_client.submit_complaint(
            self.text, self.image_paths, self.customer_name, self.customer_phone
        )
        self.finished.emit(result)


class UrgencyBadge(QLabel):
    def __init__(self, urgency_level, parent=None):
        super().__init__(parent)
        color = URGENCY_COLORS.get(urgency_level, "#95A5A6")
        label = URGENCY_LABELS.get(urgency_level, urgency_level or "未知")
        self.setText(f"  {label}  ")
        self.setStyleSheet(
            f"background-color: {color}; color: #FFFFFF; "
            f"border-radius: 10px; padding: 4px 12px; font-weight: bold; font-size: 13px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(28)


class SubmitComplaintView(QWidget):
    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._image_paths = []
        self._submit_thread = None
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(24, 24, 24, 24)
        outer_layout.setSpacing(24)

        left_widget = self._build_left_panel()
        left_widget.setFixedWidth(420)
        outer_layout.addWidget(left_widget)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        right_scroll.setStyleSheet("background-color: transparent;")
        right_content = self._build_right_panel()
        right_scroll.setWidget(right_content)
        outer_layout.addWidget(right_scroll, 1)

    def _build_left_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        title = QLabel("提交客诉信息")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1E2329;")
        layout.addWidget(title)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("客户姓名（选填）")
        self.name_input.setFixedHeight(40)
        layout.addWidget(self.name_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("联系电话（选填）")
        self.phone_input.setFixedHeight(40)
        layout.addWidget(self.phone_input)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText(
            "请输入客诉内容，如：\n订单号JD9988776655，Pro-Max-V2型号，缺少螺丝包，批次X11"
        )
        self.text_input.setMinimumHeight(160)
        self.text_input.setMaximumHeight(220)
        layout.addWidget(self.text_input)

        image_row = QHBoxLayout()
        image_row.setSpacing(12)

        self.image_btn = QPushButton("选择图片")
        self.image_btn.setProperty("secondary", True)
        self.image_btn.setFixedHeight(40)
        self.image_btn.clicked.connect(self._on_select_images)
        image_row.addWidget(self.image_btn)

        self.image_count_label = QLabel("已选择 0 张图片")
        self.image_count_label.setStyleSheet("color: #8A94A6; font-size: 13px;")
        self.image_count_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        image_row.addWidget(self.image_count_label, 1)

        layout.addLayout(image_row)

        self.submit_btn = QPushButton("提交客诉")
        self.submit_btn.setFixedHeight(48)
        self.submit_btn.setStyleSheet(
            "QPushButton { background-color: #1E2329; color: #FFFFFF; border: none; "
            "border-radius: 6px; font-size: 16px; font-weight: 600; }"
            "QPushButton:hover { background-color: #2A3038; }"
            "QPushButton:disabled { background-color: #D0D5DD; color: #FFFFFF; }"
        )
        self.submit_btn.clicked.connect(self._on_submit)
        layout.addWidget(self.submit_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 13px; min-height: 20px;")
        layout.addWidget(self.status_label)

        layout.addStretch()
        return widget

    def _build_right_panel(self):
        self.result_widget = QWidget()
        self.result_layout = QVBoxLayout(self.result_widget)
        self.result_layout.setContentsMargins(0, 0, 0, 0)
        self.result_layout.setSpacing(16)

        self.result_title = QLabel("提交结果")
        self.result_title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1E2329;")
        self.result_layout.addWidget(self.result_title)

        self.empty_hint = QLabel("请填写左侧表单并提交客诉，结果将在此处展示")
        self.empty_hint.setStyleSheet("color: #BDC3C7; font-size: 14px; padding: 60px 0;")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(self.empty_hint)

        self._overview_group = QGroupBox("工单概览")
        self._overview_form = QFormLayout(self._overview_group)
        self._overview_form.setSpacing(10)
        self._ticket_id_label = QLabel("-")
        self._urgency_container = QWidget()
        self._urgency_layout = QHBoxLayout(self._urgency_container)
        self._urgency_layout.setContentsMargins(0, 0, 0, 0)
        self._urgency_badge = QLabel("-")
        self._urgency_layout.addWidget(self._urgency_badge)
        self._urgency_layout.addStretch()
        self._status_label = QLabel("-")
        self._overview_form.addRow("工单编号：", self._ticket_id_label)
        self._overview_form.addRow("紧急度：", self._urgency_container)
        self._overview_form.addRow("工单状态：", self._status_label)
        self._overview_group.setVisible(False)
        self.result_layout.addWidget(self._overview_group)

        self._extracted_group = QGroupBox("提取数据")
        self._extracted_form = QFormLayout(self._extracted_group)
        self._extracted_form.setSpacing(10)
        self._order_id_label = QLabel("-")
        self._model_label = QLabel("-")
        self._batch_label = QLabel("-")
        self._fault_label = QLabel("-")
        self._fault_label.setWordWrap(True)
        self._extracted_form.addRow("订单号：", self._order_id_label)
        self._extracted_form.addRow("产品型号：", self._model_label)
        self._extracted_form.addRow("批次号：", self._batch_label)
        self._extracted_form.addRow("核心故障：", self._fault_label)
        self._extracted_group.setVisible(False)
        self.result_layout.addWidget(self._extracted_group)

        self._assessment_group = QGroupBox("业务评估")
        self._assessment_form = QFormLayout(self._assessment_group)
        self._assessment_form.setSpacing(10)
        self._category_label = QLabel("-")
        self._impact_label = QLabel("-")
        self._warranty_label = QLabel("-")
        self._assessment_form.addRow("问题分类：", self._category_label)
        self._assessment_form.addRow("业务影响：", self._impact_label)
        self._assessment_form.addRow("质保状态：", self._warranty_label)
        self._assessment_group.setVisible(False)
        self.result_layout.addWidget(self._assessment_group)

        self._result_group = QGroupBox("处理结果")
        self._result_form = QFormLayout(self._result_group)
        self._result_form.setSpacing(10)
        self._routing_label = QLabel("-")
        self._routing_label.setWordWrap(True)
        self._sop_label = QLabel("-")
        self._sop_label.setWordWrap(True)
        self._result_form.addRow("路由决策：", self._routing_label)
        self._result_form.addRow("匹配SOP：", self._sop_label)
        self._result_group.setVisible(False)
        self.result_layout.addWidget(self._result_group)

        self._reply_group = QGroupBox("自动回复内容")
        self._reply_layout = QVBoxLayout(self._reply_group)
        self._reply_text = QTextEdit()
        self._reply_text.setReadOnly(True)
        self._reply_text.setMinimumHeight(120)
        self._reply_text.setMaximumHeight(200)
        self._reply_text.setStyleSheet(
            "QTextEdit { background-color: #FAFBFC; border: 1px solid #EAEDF2; "
            "border-radius: 6px; padding: 10px; color: #1E2329; font-size: 13px; }"
        )
        self._reply_layout.addWidget(self._reply_text)
        self._reply_group.setVisible(False)
        self.result_layout.addWidget(self._reply_group)

        self.result_layout.addStretch()
        return self.result_widget

    def _on_select_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "", "图片文件 (*.jpg *.png *.jpeg)"
        )
        if files:
            self._image_paths = files
            self.image_count_label.setText(f"已选择 {len(files)} 张图片")

    def _on_submit(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            self.status_label.setText("请输入客诉内容")
            self.status_label.setStyleSheet("color: #FF4444; font-size: 13px;")
            return

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("提交中...")
        self.status_label.setText("正在提交客诉，请稍候...")
        self.status_label.setStyleSheet("color: #3498DB; font-size: 13px;")

        customer_name = self.name_input.text().strip() or None
        customer_phone = self.phone_input.text().strip() or None

        self._submit_thread = SubmitThread(
            self.api_client, text, self._image_paths, customer_name, customer_phone
        )
        self._submit_thread.finished.connect(self._on_submit_result)
        self._submit_thread.start()

    def _on_submit_result(self, result):
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("提交客诉")

        if result is None:
            self.status_label.setText("提交失败，请检查网络连接或后端服务是否可用")
            self.status_label.setStyleSheet("color: #FF4444; font-size: 13px;")
            return

        if result.get("code") != 0:
            self.status_label.setText(f"提交失败：{result.get('message', '未知错误')}")
            self.status_label.setStyleSheet("color: #FF4444; font-size: 13px;")
            return

        data = result.get("data", {})
        self.status_label.setText("提交成功！")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px;")
        self._display_result(data)

    def _display_result(self, data):
        self.empty_hint.setVisible(False)

        ticket_id = data.get("ticket_id", "-")
        urgency = data.get("urgency_level", "")
        status = data.get("status", "-")

        self._ticket_id_label.setText(ticket_id)
        self._ticket_id_label.setStyleSheet("font-weight: bold; color: #2C3E50;")

        old_badge = self._urgency_badge
        self._urgency_badge = UrgencyBadge(urgency)
        self._urgency_layout.replaceWidget(old_badge, self._urgency_badge)
        old_badge.deleteLater()

        self._status_label.setText(status)

        self._overview_group.setVisible(True)

        extracted = data.get("extracted_data") or {}
        self._order_id_label.setText(extracted.get("order_id") or "-")
        self._model_label.setText(extracted.get("model_number") or "-")
        self._batch_label.setText(extracted.get("batch_code") or "-")
        self._fault_label.setText(extracted.get("core_fault_desc") or "-")
        self._extracted_group.setVisible(True)

        assessment = data.get("agent_business_assessment") or {}
        self._category_label.setText(assessment.get("issue_category") or "-")
        self._impact_label.setText(assessment.get("business_impact") or "-")
        self._warranty_label.setText(assessment.get("warranty_status") or "-")
        self._assessment_group.setVisible(True)

        routing = data.get("routing_decision") or "-"
        sop = data.get("sop_applied") or "-"
        self._routing_label.setText(str(routing))
        self._sop_label.setText(str(sop))
        self._result_group.setVisible(True)

        reply = data.get("auto_reply_sent") or ""
        self._reply_text.setPlainText(str(reply) if reply else "（无自动回复）")
        self._reply_group.setVisible(True)
