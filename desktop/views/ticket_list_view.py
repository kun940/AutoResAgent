import os
import tempfile

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QComboBox, QSpinBox, QGroupBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QSizePolicy, QDialog, QDialogButtonBox, QMessageBox,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from desktop.api_client import ApiClient
from shared.constants import TICKET_STATUS_TRANSITIONS, TicketStatus


CATEGORY_MAP = {
    "Missing_Parts": "配件缺失",
    "Operation_Error": "操作错误",
    "Software_Bug": "软件缺陷",
    "Hardware_Malfunction": "硬件故障",
    "Hardware_Thermal_Runaway": "热失控",
    "Electrical_Leakage": "漏电问题",
    "Batch_Defect": "批次缺陷",
    "Safety_Hazard": "安全隐患",
    "Other": "其他",
}

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

STATUS_COLORS = {
    "pending": ("#FFF3CD", "#856404"),
    "processing": ("#D6EAF8", "#2471A3"),
    "routed": ("#E8DAEF", "#7D3C98"),
    "resolved": ("#D5F5E3", "#1E8449"),
    "closed": ("#F2F3F4", "#7F8C8D"),
    "cancelled": ("#F2F3F4", "#BDC3C7"),
}

STATUS_LABELS = {
    "pending": "待处理",
    "processing": "处理中",
    "routed": "已路由",
    "resolved": "已解决",
    "closed": "已关闭",
    "cancelled": "已取消",
}

ROLE_OPTIONS = {
    "一线客服": "frontline_staff",
    "部门主管": "department_manager",
    "总经理": "general_manager",
    "管理员": "admin",
}


class LoadTicketsThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, status=None, urgency_level=None, target_role=None, page=1, page_size=20):
        super().__init__()
        self.api_client = api_client
        self.status = status
        self.urgency_level = urgency_level
        self.target_role = target_role
        self.page = page
        self.page_size = page_size

    def run(self):
        result = self.api_client.get_tickets(
            status=self.status, urgency_level=self.urgency_level,
            target_role=self.target_role,
            page=self.page, page_size=self.page_size
        )
        self.finished.emit(result)


class ActionThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception:
            self.finished.emit(None)


class ImageLoadThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, url, thumb):
        super().__init__()
        self.url = url
        self.thumb = thumb

    def run(self):
        try:
            import requests as req
            resp = req.get(self.url, timeout=10)
            if resp.status_code != 200 or not resp.content:
                self.finished.emit({"thumb": self.thumb, "thumb_path": None, "preview_path": None})
                return

            tmp_dir = os.path.join(tempfile.gettempdir(), "complaint_images")
            os.makedirs(tmp_dir, exist_ok=True)
            url_hash = abs(hash(self.url)) % 1000000

            thumb_path = os.path.join(tmp_dir, f"{url_hash}_thumb.png")
            preview_path = os.path.join(tmp_dir, f"{url_hash}_preview.png")

            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(resp.content))
            img = img.convert("RGBA")

            thumb_img = img.copy()
            thumb_img.thumbnail((120, 120), Image.LANCZOS)
            thumb_img.save(thumb_path, "PNG")

            preview_img = img.copy()
            preview_img.thumbnail((800, 600), Image.LANCZOS)
            preview_img.save(preview_path, "PNG")

            self.finished.emit({"thumb": self.thumb, "thumb_path": thumb_path, "preview_path": preview_path})
        except Exception:
            self.finished.emit({"thumb": self.thumb, "thumb_path": None, "preview_path": None})


class TicketDetailThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, ticket_id):
        super().__init__()
        self.api_client = api_client
        self.ticket_id = ticket_id

    def run(self):
        result = self.api_client.get_ticket(self.ticket_id)
        self.finished.emit(result)


class UrgencyBadge(QLabel):
    def __init__(self, urgency_level, parent=None):
        super().__init__(parent)
        color = URGENCY_COLORS.get(urgency_level, "#95A5A6")
        label = URGENCY_LABELS.get(urgency_level, urgency_level or "未知")
        self.setText(f"  {label}  ")
        self.setStyleSheet(
            f"background-color: {color}; color: #FFFFFF; "
            f"border-radius: 10px; padding: 4px 12px; font-weight: bold; font-size: 12px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(26)


class StatusBadge(QLabel):
    def __init__(self, status, parent=None):
        super().__init__(parent)
        bg, fg = STATUS_COLORS.get(status, ("#F2F3F4", "#7F8C8D"))
        label = STATUS_LABELS.get(status, status or "未知")
        self.setText(f"  {label}  ")
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"border-radius: 10px; padding: 4px 12px; font-weight: bold; font-size: 12px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(26)


class StatusChangeDialog(QDialog):
    def __init__(self, current_status, parent=None):
        super().__init__(parent)
        self.setWindowTitle("变更工单状态")
        self.setMinimumWidth(360)
        self._result = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.status_combo = QComboBox()
        transitions = TICKET_STATUS_TRANSITIONS.get(TicketStatus(current_status), [])
        for ts in transitions:
            self.status_combo.addItem(STATUS_LABELS.get(ts.value, ts.value), ts.value)
        if self.status_combo.count() == 0:
            self.status_combo.addItem("无可用状态", "")
        form.addRow("新状态：", self.status_combo)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("备注（选填）")
        self.note_edit.setMaximumHeight(80)
        form.addRow("备注：", self.note_edit)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self):
        self._result = {
            "status": self.status_combo.currentData(),
            "note": self.note_edit.toPlainText().strip() or None,
        }
        self.accept()

    def get_result(self):
        return self._result


class EscalateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("升级工单")
        self.setMinimumWidth(360)
        self._result = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.level_combo = QComboBox()
        self.level_combo.addItem("中紧急", "Medium_Priority")
        self.level_combo.addItem("高紧急", "High_Priority")
        form.addRow("目标紧急度：", self.level_combo)

        self.reason_edit = QTextEdit()
        self.reason_edit.setPlaceholderText("升级原因（必填）")
        self.reason_edit.setMaximumHeight(80)
        form.addRow("原因：", self.reason_edit)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self):
        reason = self.reason_edit.toPlainText().strip()
        if not reason:
            QMessageBox.warning(self, "提示", "请填写升级原因")
            return
        self._result = {
            "to_level": self.level_combo.currentData(),
            "reason": reason,
        }
        self.accept()

    def get_result(self):
        return self._result


class ReassignDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("转派工单")
        self.setMinimumWidth(360)
        self._result = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.role_combo = QComboBox()
        for label, value in ROLE_OPTIONS.items():
            self.role_combo.addItem(label, value)
        form.addRow("目标角色：", self.role_combo)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("输入目标用户的用户名")
        form.addRow("用户名：", self.username_edit)

        self.reason_edit = QTextEdit()
        self.reason_edit.setPlaceholderText("转派原因（必填）")
        self.reason_edit.setMaximumHeight(80)
        form.addRow("原因：", self.reason_edit)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self):
        username = self.username_edit.text().strip()
        reason = self.reason_edit.toPlainText().strip()
        if not username:
            QMessageBox.warning(self, "提示", "请输入目标用户名")
            return
        if not reason:
            QMessageBox.warning(self, "提示", "请填写转派原因")
            return
        self._result = {
            "target_username": username,
            "target_role": self.role_combo.currentData(),
            "reason": reason,
        }
        self.accept()

    def get_result(self):
        return self._result


class ImagePreviewDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("证据图片")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        img_label = QLabel()
        pixmap = QPixmap(image_path)
        img_label.setFixedSize(
            min(pixmap.width(), 800) if not pixmap.isNull() else 800,
            min(pixmap.height(), 600) if not pixmap.isNull() else 600
        )
        img_label.setScaledContents(True)
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class ThumbnailLabel(QLabel):
    clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "QLabel { background-color: #F0F0F0; border: 1px solid #DDD; border-radius: 4px; "
            "color: #BDC3C7; font-size: 12px; }"
        )
        self.setText("加载中...")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_path = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._preview_path:
            self.clicked.emit(self._preview_path)
        super().mousePressEvent(event)

    def set_pixmap(self, pixmap, preview_path=None):
        self._preview_path = preview_path
        self.setScaledContents(True)
        self.setPixmap(pixmap)
        self.setStyleSheet(
            "QLabel { background-color: #FFFFFF; border: 1px solid #DDD; border-radius: 4px; }"
        )

    def set_load_failed(self):
        self.setText("加载失败")
        self.setStyleSheet(
            "QLabel { background-color: #FFF3CD; border: 1px solid #FFEEBA; border-radius: 4px; "
            "color: #856404; font-size: 12px; }"
        )


class TicketListView(QWidget):
    def __init__(self, api_client: ApiClient, role=None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._role = role
        self._current_page = 1
        self._total_pages = 1
        self._total_count = 0
        self._tickets = []
        self._selected_ticket = None
        self._load_thread = None
        self._action_thread = None
        self._image_loaders = []
        self._image_version = 0
        self._detail_thread = None
        self._setup_ui()
        self._load_tickets()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        filter_layout.addWidget(QLabel("状态："))
        self.status_combo = QComboBox()
        self.status_combo.addItem("全部", "")
        self.status_combo.addItem("待处理", "pending")
        self.status_combo.addItem("处理中", "processing")
        self.status_combo.addItem("已路由", "routed")
        self.status_combo.addItem("已解决", "resolved")
        self.status_combo.addItem("已关闭", "closed")
        self.status_combo.addItem("已取消", "cancelled")
        self.status_combo.setFixedWidth(140)
        filter_layout.addWidget(self.status_combo)

        filter_layout.addWidget(QLabel("紧急度："))
        self.urgency_combo = QComboBox()
        self.urgency_combo.addItem("全部", "")
        self.urgency_combo.addItem("高紧急", "High_Priority")
        self.urgency_combo.addItem("中紧急", "Medium_Priority")
        self.urgency_combo.addItem("低紧急", "Low_Priority")
        self.urgency_combo.setFixedWidth(140)
        filter_layout.addWidget(self.urgency_combo)

        self.search_btn = QPushButton("查询")
        self.search_btn.clicked.connect(self._on_search)
        filter_layout.addWidget(self.search_btn)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self._on_reset)
        filter_layout.addWidget(self.reset_btn)

        filter_layout.addStretch()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._on_refresh)
        filter_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(filter_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["工单编号", "客户", "紧急度", "状态", "问题分类", "创建时间"])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 120)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self._on_row_clicked)
        content_layout.addWidget(self.table, 1)

        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFixedWidth(360)
        detail_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        detail_scroll.setStyleSheet("background-color: transparent;")
        self.detail_widget = self._build_detail_panel()
        detail_scroll.setWidget(self.detail_widget)
        content_layout.addWidget(detail_scroll)

        main_layout.addLayout(content_layout, 1)

        page_layout = QHBoxLayout()
        self.total_label = QLabel("共 0 条记录")
        self.total_label.setStyleSheet("color: #7F8C8D; font-size: 13px;")
        page_layout.addWidget(self.total_label)
        page_layout.addStretch()

        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self._on_prev_page)
        page_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("第 1 / 1 页")
        self.page_label.setStyleSheet("color: #2C3E50; font-size: 13px; padding: 0 12px;")
        page_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self._on_next_page)
        page_layout.addWidget(self.next_btn)

        main_layout.addLayout(page_layout)

    def _build_detail_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.detail_hint = QLabel("请选择工单查看详情")
        self.detail_hint.setStyleSheet("color: #BDC3C7; font-size: 14px; padding: 40px 0;")
        self.detail_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_hint)

        self.detail_overview = QGroupBox("工单概览")
        form1 = QFormLayout(self.detail_overview)
        form1.setSpacing(8)
        self.d_ticket_id = QLabel("-")
        self.d_urgency = QLabel("-")
        self.d_status = QLabel("-")
        self.d_created = QLabel("-")
        self.d_resolved = QLabel("-")
        form1.addRow("工单编号：", self.d_ticket_id)
        form1.addRow("紧急度：", self.d_urgency)
        form1.addRow("状态：", self.d_status)
        form1.addRow("创建时间：", self.d_created)
        form1.addRow("解决时间：", self.d_resolved)
        self.detail_overview.setVisible(False)
        layout.addWidget(self.detail_overview)

        self.detail_customer = QGroupBox("客户信息")
        form2 = QFormLayout(self.detail_customer)
        form2.setSpacing(8)
        self.d_name = QLabel("-")
        self.d_phone = QLabel("-")
        form2.addRow("客户姓名：", self.d_name)
        form2.addRow("联系电话：", self.d_phone)
        self.detail_customer.setVisible(False)
        layout.addWidget(self.detail_customer)

        self.detail_extracted = QGroupBox("提取数据")
        form3 = QFormLayout(self.detail_extracted)
        form3.setSpacing(8)
        self.d_order = QLabel("-")
        self.d_model = QLabel("-")
        self.d_batch = QLabel("-")
        self.d_fault = QLabel("-")
        self.d_fault.setWordWrap(True)
        form3.addRow("订单号：", self.d_order)
        form3.addRow("产品型号：", self.d_model)
        form3.addRow("批次号：", self.d_batch)
        form3.addRow("核心故障：", self.d_fault)
        self.detail_extracted.setVisible(False)
        layout.addWidget(self.detail_extracted)

        self.detail_assessment = QGroupBox("业务评估")
        form4 = QFormLayout(self.detail_assessment)
        form4.setSpacing(8)
        self.d_category = QLabel("-")
        self.d_impact = QLabel("-")
        self.d_warranty = QLabel("-")
        form4.addRow("问题分类：", self.d_category)
        form4.addRow("业务影响：", self.d_impact)
        form4.addRow("质保状态：", self.d_warranty)
        self.detail_assessment.setVisible(False)
        layout.addWidget(self.detail_assessment)

        self.detail_process = QGroupBox("处理信息")
        form5 = QFormLayout(self.detail_process)
        form5.setSpacing(8)
        self.d_routing = QLabel("-")
        self.d_routing.setWordWrap(True)
        self.d_sop = QLabel("-")
        self.d_sop.setWordWrap(True)
        form5.addRow("路由决策：", self.d_routing)
        form5.addRow("匹配SOP：", self.d_sop)
        self.detail_process.setVisible(False)
        layout.addWidget(self.detail_process)

        self.detail_reply = QGroupBox("自动回复")
        reply_layout = QVBoxLayout(self.detail_reply)
        self.d_reply = QTextEdit()
        self.d_reply.setReadOnly(True)
        self.d_reply.setMaximumHeight(100)
        self.d_reply.setStyleSheet(
            "QTextEdit { background-color: #F8F9FA; border: 1px solid #E0E0E0; "
            "border-radius: 4px; padding: 8px; font-size: 12px; }"
        )
        reply_layout.addWidget(self.d_reply)
        self.detail_reply.setVisible(False)
        layout.addWidget(self.detail_reply)

        self.detail_evidence = QGroupBox("证据图片")
        self.evidence_layout = QVBoxLayout(self.detail_evidence)
        self.evidence_layout.setSpacing(8)
        self.d_evidence_hint = QLabel("暂无图片")
        self.d_evidence_hint.setStyleSheet("color: #BDC3C7; font-size: 13px;")
        self.d_evidence_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.evidence_layout.addWidget(self.d_evidence_hint)
        self.detail_evidence.setVisible(False)
        layout.addWidget(self.detail_evidence)

        self.action_layout = QHBoxLayout()
        self.btn_change_status = QPushButton("变更状态")
        self.btn_change_status.setStyleSheet(
            "QPushButton { background-color: #3498DB; color: #FFFFFF; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #2980B9; }"
        )
        self.btn_change_status.clicked.connect(self._on_change_status)
        self.action_layout.addWidget(self.btn_change_status)

        self.btn_escalate = QPushButton("升级工单")
        self.btn_escalate.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: #FFFFFF; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )
        self.btn_escalate.clicked.connect(self._on_escalate)
        self.action_layout.addWidget(self.btn_escalate)

        self.btn_reassign = QPushButton("转派工单")
        self.btn_reassign.setStyleSheet(
            "QPushButton { background-color: #9B59B6; color: #FFFFFF; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #8E44AD; }"
        )
        self.btn_reassign.clicked.connect(self._on_reassign)
        self.action_layout.addWidget(self.btn_reassign)

        self.action_widget = QWidget()
        self.action_widget.setLayout(self.action_layout)
        self.action_widget.setVisible(False)
        layout.addWidget(self.action_widget)

        layout.addStretch()
        return widget

    def _load_tickets(self):
        self._set_controls_enabled(False)
        status = self.status_combo.currentData() or None
        urgency = self.urgency_combo.currentData() or None

        self._load_thread = LoadTicketsThread(
            self.api_client, status, urgency, self._role, self._current_page, 20
        )
        self._load_thread.finished.connect(self._on_tickets_loaded)
        self._load_thread.start()

    def _set_controls_enabled(self, enabled):
        self.search_btn.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        self.prev_btn.setEnabled(enabled and self._current_page > 1)
        self.next_btn.setEnabled(enabled and self._current_page < self._total_pages)

    def _on_tickets_loaded(self, result):
        self._set_controls_enabled(True)

        if result is None:
            self.table.setRowCount(0)
            self.total_label.setText("无法加载工单数据")
            self.total_label.setStyleSheet("color: #FF4444; font-size: 13px;")
            return

        total = result.get("total", 0)
        self._total_count = total
        self._total_pages = max(1, (total + 19) // 20)
        self._tickets = result.get("data", [])

        self.total_label.setText(f"共 {total} 条记录")
        self.total_label.setStyleSheet("color: #7F8C8D; font-size: 13px;")
        self.page_label.setText(f"第 {self._current_page} / {self._total_pages} 页")

        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self._tickets))
        for row, ticket in enumerate(self._tickets):
            item_id = QTableWidgetItem(ticket.get("ticket_id", "-"))
            self.table.setItem(row, 0, item_id)

            item_name = QTableWidgetItem(ticket.get("customer_name") or "未知")
            self.table.setItem(row, 1, item_name)

            urgency = ticket.get("urgency_level", "")
            badge = UrgencyBadge(urgency)
            self.table.setCellWidget(row, 2, badge)

            status = ticket.get("status", "")
            status_badge = StatusBadge(status)
            self.table.setCellWidget(row, 3, status_badge)

            category = ticket.get("issue_category", "")
            cat_text = CATEGORY_MAP.get(category, category or "-")
            item_cat = QTableWidgetItem(cat_text)
            self.table.setItem(row, 4, item_cat)

            created = ticket.get("created_at", "-")
            if created and len(created) >= 16:
                created = created[:16].replace("T", " ")
            item_time = QTableWidgetItem(created)
            self.table.setItem(row, 5, item_time)

        self.table.setRowHeight(0, 36)
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 36)

    def _on_row_clicked(self, row, col):
        if row < 0 or row >= len(self._tickets):
            return
        self._selected_ticket = self._tickets[row]
        ticket_id = self._selected_ticket.get("ticket_id")
        if ticket_id:
            if self._detail_thread and self._detail_thread.isRunning():
                try:
                    self._detail_thread.finished.disconnect()
                except Exception:
                    pass
            self._detail_thread = TicketDetailThread(self.api_client, ticket_id)
            self._detail_thread.finished.connect(self._on_detail_loaded)
            self._detail_thread.start()
        else:
            self._show_detail(self._selected_ticket)

    def _on_detail_loaded(self, result):
        if result and result.get("code") == 0:
            data = result.get("data")
            if data:
                self._selected_ticket = data
                self._show_detail(data)

    def _show_detail(self, ticket):
        self.detail_hint.setVisible(False)
        self.detail_overview.setVisible(True)
        self.detail_customer.setVisible(True)
        self.detail_extracted.setVisible(True)
        self.detail_assessment.setVisible(True)
        self.detail_process.setVisible(True)
        self.detail_reply.setVisible(True)
        self.detail_evidence.setVisible(True)
        self.action_widget.setVisible(True)

        self.d_ticket_id.setText(ticket.get("ticket_id", "-"))
        self.d_ticket_id.setStyleSheet("font-weight: bold;")

        urgency = ticket.get("urgency_level", "")
        old = self.d_urgency
        self.d_urgency = UrgencyBadge(urgency)
        parent_layout = old.parent().layout()
        if parent_layout:
            idx = parent_layout.indexOf(old)
            parent_layout.replaceWidget(old, self.d_urgency)
            old.deleteLater()

        status = ticket.get("status", "-")
        old_s = self.d_status
        self.d_status = StatusBadge(status)
        parent_layout_s = old_s.parent().layout()
        if parent_layout_s:
            parent_layout_s.replaceWidget(old_s, self.d_status)
            old_s.deleteLater()

        created = ticket.get("created_at", "-")
        if created and len(created) >= 16:
            created = created[:16].replace("T", " ")
        self.d_created.setText(created)

        resolved = ticket.get("resolved_at")
        if resolved and len(resolved) >= 16:
            resolved = resolved[:16].replace("T", " ")
        self.d_resolved.setText(resolved or "-")

        self.d_name.setText(ticket.get("customer_name") or "-")
        self.d_phone.setText(ticket.get("customer_phone") or "-")

        extracted = ticket.get("extracted_data") or {}
        self.d_order.setText(extracted.get("order_id") or "-")
        self.d_model.setText(extracted.get("model_number") or "-")
        self.d_batch.setText(extracted.get("batch_code") or "-")
        self.d_fault.setText(extracted.get("core_fault_desc") or "-")

        assessment = ticket.get("agent_business_assessment") or {}
        self.d_category.setText(CATEGORY_MAP.get(assessment.get("issue_category"), assessment.get("issue_category") or "-"))
        self.d_impact.setText(assessment.get("business_impact") or "-")
        self.d_warranty.setText(assessment.get("warranty_status") or "-")

        self.d_routing.setText(str(ticket.get("routing_decision") or "-"))
        self.d_sop.setText(str(ticket.get("sop_applied") or "-"))

        reply = ticket.get("auto_reply_sent") or ""
        self.d_reply.setPlainText(str(reply) if reply else "（无自动回复）")

        self._load_evidence_images(ticket)

    def _load_evidence_images(self, ticket):
        self._image_version += 1
        current_version = self._image_version

        for loader in self._image_loaders:
            try:
                loader.finished.disconnect()
            except Exception:
                pass
        self._image_loaders.clear()

        while self.evidence_layout.count():
            item = self.evidence_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            layout = item.layout()
            if layout:
                while layout.count():
                    sub = layout.takeAt(0)
                    w = sub.widget()
                    if w:
                        w.deleteLater()

        images = ticket.get("evidence_images") or []
        if not images:
            self.d_evidence_hint = QLabel("暂无图片")
            self.d_evidence_hint.setStyleSheet("color: #BDC3C7; font-size: 13px;")
            self.d_evidence_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.evidence_layout.addWidget(self.d_evidence_hint)
            return

        row_layout = QHBoxLayout()
        row_layout.setSpacing(8)
        for img_path in images:
            base_url = self.api_client.base_url.rsplit("/api", 1)[0]
            full_url = f"{base_url}{img_path}"

            thumb = ThumbnailLabel()
            thumb.clicked.connect(self._show_image_preview)
            row_layout.addWidget(thumb)

            loader = ImageLoadThread(full_url, thumb)
            loader.finished.connect(lambda result, v=current_version: self._on_image_thread_done(result, v))
            loader.start()
            self._image_loaders.append(loader)

        self.evidence_layout.addLayout(row_layout)

    def _on_image_thread_done(self, result, version):
        if version != self._image_version:
            return
        thumb = result["thumb"]
        thumb_path = result.get("thumb_path")
        preview_path = result.get("preview_path")
        if thumb_path and os.path.exists(thumb_path):
            pixmap = QPixmap(thumb_path)
            if not pixmap.isNull():
                thumb.set_pixmap(pixmap, preview_path)
                return
        thumb.set_load_failed()

    def _show_image_preview(self, preview_path):
        if preview_path and os.path.exists(preview_path):
            dialog = ImagePreviewDialog(preview_path, self)
            dialog.exec()

    def _on_search(self):
        self._current_page = 1
        self._load_tickets()

    def _on_reset(self):
        self.status_combo.setCurrentIndex(0)
        self.urgency_combo.setCurrentIndex(0)
        self._current_page = 1
        self._load_tickets()

    def _on_refresh(self):
        self._load_tickets()

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_tickets()

    def _on_next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_tickets()

    def _on_change_status(self):
        if not self._selected_ticket:
            return
        dialog = StatusChangeDialog(self._selected_ticket.get("status", "pending"), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result and result.get("status"):
                self._exec_action(
                    self.api_client.update_ticket_status,
                    self._selected_ticket["ticket_id"],
                    result["status"],
                    result.get("note")
                )

    def _on_escalate(self):
        if not self._selected_ticket:
            return
        dialog = EscalateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                self._exec_action(
                    self.api_client.escalate_ticket,
                    self._selected_ticket["ticket_id"],
                    result["to_level"],
                    result["reason"]
                )

    def _on_reassign(self):
        if not self._selected_ticket:
            return
        dialog = ReassignDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                self._exec_action(
                    self.api_client.reassign_ticket,
                    self._selected_ticket["ticket_id"],
                    result["target_username"],
                    result["target_role"],
                    result["reason"]
                )

    def _exec_action(self, func, *args):
        self._set_controls_enabled(False)
        self._action_thread = ActionThread(func, *args)
        self._action_thread.finished.connect(self._on_action_done)
        self._action_thread.start()

    def _on_action_done(self, result):
        self._set_controls_enabled(True)
        if result is None:
            QMessageBox.warning(self, "操作失败", "操作失败，请检查网络连接或后端服务")
        elif result.get("code") != 0:
            QMessageBox.warning(self, "操作失败", result.get("message", "未知错误"))
        else:
            QMessageBox.information(self, "操作成功", "操作已成功执行")
            self._load_tickets()
