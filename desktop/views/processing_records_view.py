from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDateEdit, QCheckBox, QFrame, QScrollArea, QGroupBox, QFormLayout,
    QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate

from desktop.api_client import ApiClient


# ===== 常量映射（与 ticket_list_view 保持一致，避免循环依赖在此重声明）=====

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

URGENCY_LABELS = {
    "High_Priority": "高紧急",
    "Medium_Priority": "中紧急",
    "Low_Priority": "低紧急",
}

URGENCY_COLORS = {
    "High_Priority": "#FF4444",
    "Medium_Priority": "#FF9800",
    "Low_Priority": "#4CAF50",
}

STATUS_LABELS = {
    "pending": "待处理",
    "processing": "处理中",
    "routed": "已路由",
    "resolved": "已解决",
    "closed": "已关闭",
    "cancelled": "已取消",
}

STATUS_COLORS = {
    "pending": ("#FFF3CD", "#856404"),
    "processing": ("#D6EAF8", "#2471A3"),
    "routed": ("#E8DAEF", "#7D3C98"),
    "resolved": ("#D5F5E3", "#1E8449"),
    "closed": ("#F2F3F4", "#7F8C8D"),
    "cancelled": ("#F2F3F4", "#BDC3C7"),
}

ROLE_LABELS = {
    "frontline_staff": "一线客服",
    "department_manager": "部门主管",
    "general_manager": "总经理",
    "admin": "管理员",
}

IMPACT_MAP = {
    "No_Impact": "无影响",
    "Minor_Inconvenience": "轻微不便",
    "Functional_Loss": "功能丧失",
    "Production_Down": "生产停滞",
    "Safety_Hazard": "安全隐患",
    "Group_Risk": "集团风险",
}

WARRANTY_MAP = {
    "In_Warranty": "保内",
    "Out_of_Warranty": "保外",
    "Unknown": "未知",
}

# 所有可翻译映射的合并表（用于变更摘要中英文值 → 中文替换）
_TRANSLATE_MAP = {}
_TRANSLATE_MAP.update(STATUS_LABELS)
_TRANSLATE_MAP.update(URGENCY_LABELS)
_TRANSLATE_MAP.update(CATEGORY_MAP)
_TRANSLATE_MAP.update(ROLE_LABELS)

# 操作类型 -> 中文标签
ACTION_LABELS = {
    "status_change": "变更状态",
    "escalation": "升级工单",
    "reassign": "转派工单",
}

# 操作类型 -> (背景色, 前景色)
ACTION_COLORS = {
    "status_change": ("#D6EAF8", "#2471A3"),
    "escalation": ("#FDEBD0", "#B9770E"),
    "reassign": ("#E8DAEF", "#7D3C98"),
}


class LoadProcessingRecordsThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, page=1, page_size=20, start_date=None, end_date=None):
        super().__init__()
        self.api_client = api_client
        self.page = page
        self.page_size = page_size
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        result = self.api_client.get_processing_records(
            page=self.page,
            page_size=self.page_size,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        self.finished.emit(result)


class TicketDetailThread(QThread):
    """加载工单完整详情"""
    finished = pyqtSignal(object)

    def __init__(self, api_client, ticket_id):
        super().__init__()
        self.api_client = api_client
        self.ticket_id = ticket_id

    def run(self):
        result = self.api_client.get_ticket(self.ticket_id)
        self.finished.emit(result)


class ActionBadge(QLabel):
    """操作类型标签（仿 UrgencyBadge，带配色）"""

    def __init__(self, action, parent=None):
        super().__init__(parent)
        label = ACTION_LABELS.get(action, action or "未知")
        bg, fg = ACTION_COLORS.get(action, ("#F2F3F4", "#7F8C8D"))
        self.setText(f"  {label}  ")
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"border-radius: 10px; padding: 4px 12px; font-weight: bold; font-size: 12px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(26)


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


def _format_datetime(value):
    """将后端返回的时间字符串格式化为 'YYYY-MM-DD HH:MM:SS'"""
    if not value:
        return "-"
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1]
        dt = datetime.fromisoformat(text)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        text = str(value)
        if len(text) >= 16:
            return text[:16].replace("T", " ")
        return text


def _translate_summary(text):
    """将变更摘要中的英文枚举值替换为中文标签"""
    if not text or text == "-":
        return text
    result = text
    for en, cn in _TRANSLATE_MAP.items():
        result = result.replace(en, cn)
    return result


class ProcessingRecordsView(QWidget):
    """处理记录页面：左侧列表 + 右侧详情面板（工单信息 + 变更详情）"""

    def __init__(self, api_client: ApiClient, role=None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._role = role
        self._current_page = 1
        self._total_pages = 1
        self._page_size = 20
        self._records = []
        self._selected_record = None
        self._selected_ticket_detail = None
        self._load_thread = None
        self._detail_thread = None
        self._loaded_once = False
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 顶栏标题
        title_label = QLabel("处理记录")
        title_label.setObjectName("page_title")
        main_layout.addWidget(title_label)

        subtitle_label = QLabel("查看您对工单执行的处理操作历史（变更状态 / 升级 / 转派）")
        subtitle_label.setObjectName("page_subtitle")
        main_layout.addWidget(subtitle_label)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #EAEDF2; background-color: #EAEDF2; max-height: 1px;")
        main_layout.addWidget(sep)

        # 过滤栏
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.date_filter_check = QCheckBox("按日期筛选：")
        self.date_filter_check.setCursor(Qt.CursorShape.PointingHandCursor)
        filter_layout.addWidget(self.date_filter_check)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.start_date_edit.setFixedWidth(140)
        self.start_date_edit.setEnabled(False)
        filter_layout.addWidget(self.start_date_edit)

        filter_layout.addWidget(QLabel("至"))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setFixedWidth(140)
        self.end_date_edit.setEnabled(False)
        filter_layout.addWidget(self.end_date_edit)

        self.date_filter_check.toggled.connect(self._on_date_filter_toggled)

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

        # ===== 左右分栏：左侧表格 + 右侧详情 =====
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # 左侧：表格（精简列，详情移到右侧面板）
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "处理时间", "操作类型", "工单编号", "客户 / 问题分类"
        ])
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 150)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self._on_row_clicked)
        content_layout.addWidget(self.table, 1)

        # 右侧：详情面板（可滚动）
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFixedWidth(360)
        detail_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        detail_scroll.setStyleSheet("background-color: transparent;")
        self.detail_widget = self._build_detail_panel()
        detail_scroll.setWidget(self.detail_widget)
        content_layout.addWidget(detail_scroll)

        main_layout.addLayout(content_layout, 1)

        # 分页栏
        page_layout = QHBoxLayout()
        self.total_label = QLabel("共 0 条记录")
        self.total_label.setStyleSheet("color: #8A94A6; font-size: 13px;")
        page_layout.addWidget(self.total_label)
        page_layout.addStretch()

        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self._on_prev_page)
        page_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("第 1 / 1 页")
        self.page_label.setStyleSheet("color: #1E2329; font-size: 13px; padding: 0 12px;")
        page_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self._on_next_page)
        page_layout.addWidget(self.next_btn)

        main_layout.addLayout(page_layout)

    def _build_detail_panel(self):
        """构建右侧详情面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 提示文字（未选中时显示）
        self.detail_hint = QLabel("请选择一条处理记录查看详情")
        self.detail_hint.setStyleSheet("color: #BDC3C7; font-size: 14px; padding: 40px 0;")
        self.detail_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_hint)

        # ----- 变更详情 -----
        self.detail_change = QGroupBox("变更详情")
        form_change = QFormLayout(self.detail_change)
        form_change.setSpacing(8)

        self.d_action = QLabel("-")
        form_change.addRow("操作类型：", self.d_action)

        self.d_summary = QLabel("-")
        self.d_summary.setWordWrap(True)
        form_change.addRow("变更摘要：", self.d_summary)

        self.d_reason = QTextEdit()
        self.d_reason.setReadOnly(True)
        self.d_reason.setPlainText("-")
        self.d_reason.setMinimumHeight(60)
        self.d_reason.setMaximumHeight(120)
        self.d_reason.setStyleSheet(
            "QTextEdit { background-color: #FAFBFC; border: 1px solid #EAEDF2; "
            "border-radius: 6px; padding: 8px; font-size: 12px; }"
        )
        form_change.addRow("变更原因：", self.d_reason)

        self.d_operator = QLabel("-")
        form_change.addRow("操作人：", self.d_operator)

        self.d_time = QLabel("-")
        form_change.addRow("操作时间：", self.d_time)

        self.detail_change.setVisible(False)
        layout.addWidget(self.detail_change)

        # ----- 工单概览 -----
        self.detail_overview = QGroupBox("工单概览")
        form1 = QFormLayout(self.detail_overview)
        form1.setSpacing(8)

        self.d_ticket_id = QLabel("-")
        self.d_ticket_id.setStyleSheet("font-weight: bold;")
        form1.addRow("工单编号：", self.d_ticket_id)

        self.d_status = QLabel("-")
        form1.addRow("状态：", self.d_status)

        self.d_urgency = QLabel("-")
        form1.addRow("紧急度：", self.d_urgency)

        self.d_created = QLabel("-")
        form1.addRow("创建时间：", self.d_created)

        self.d_resolved = QLabel("-")
        form1.addRow("解决时间：", self.d_resolved)

        self.detail_overview.setVisible(False)
        layout.addWidget(self.detail_overview)

        # ----- 客户信息 -----
        self.detail_customer = QGroupBox("客户信息")
        form2 = QFormLayout(self.detail_customer)
        form2.setSpacing(8)

        self.d_name = QLabel("-")
        form2.addRow("客户姓名：", self.d_name)

        self.d_phone = QLabel("-")
        form2.addRow("联系电话：", self.d_phone)

        self.detail_customer.setVisible(False)
        layout.addWidget(self.detail_customer)

        # ----- 业务评估 -----
        self.detail_assessment = QGroupBox("业务评估")
        form3 = QFormLayout(self.detail_assessment)
        form3.setSpacing(8)

        self.d_category = QLabel("-")
        form3.addRow("问题分类：", self.d_category)

        self.d_impact = QLabel("-")
        form3.addRow("业务影响：", self.d_impact)

        self.d_warranty = QLabel("-")
        form3.addRow("质保状态：", self.d_warranty)

        self.detail_assessment.setVisible(False)
        layout.addWidget(self.detail_assessment)

        # ----- 提取数据 -----
        self.detail_extracted = QGroupBox("提取数据")
        form4 = QFormLayout(self.detail_extracted)
        form4.setSpacing(8)

        self.d_order = QLabel("-")
        form4.addRow("订单号：", self.d_order)

        self.d_model = QLabel("-")
        form4.addRow("产品型号：", self.d_model)

        self.d_batch = QLabel("-")
        form4.addRow("批次号：", self.d_batch)

        self.d_fault = QTextEdit()
        self.d_fault.setReadOnly(True)
        self.d_fault.setPlainText("-")
        self.d_fault.setMinimumHeight(50)
        self.d_fault.setMaximumHeight(100)
        self.d_fault.setStyleSheet(
            "QTextEdit { background-color: #FAFBFC; border: 1px solid #EAEDF2; "
            "border-radius: 6px; padding: 8px; font-size: 12px; }"
        )
        form4.addRow("核心故障：", self.d_fault)

        self.detail_extracted.setVisible(False)
        layout.addWidget(self.detail_extracted)

        layout.addStretch()
        return widget

    def _on_date_filter_toggled(self, checked):
        self.start_date_edit.setEnabled(checked)
        self.end_date_edit.setEnabled(checked)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded_once:
            self._loaded_once = True
            self._load()

    # ===== 数据加载 =====

    def _get_date_params(self):
        if not self.date_filter_check.isChecked():
            return None, None
        start = self.start_date_edit.date().toString("yyyy-MM-dd")
        end = self.end_date_edit.date().toString("yyyy-MM-dd")
        return start, end

    def _load(self):
        self._set_controls_enabled(False)
        start, end = self._get_date_params()
        self._load_thread = LoadProcessingRecordsThread(
            self.api_client,
            page=self._current_page,
            page_size=self._page_size,
            start_date=start,
            end_date=end,
        )
        self._load_thread.finished.connect(self._on_loaded)
        self._load_thread.start()

    def _set_controls_enabled(self, enabled):
        self.search_btn.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        self.date_filter_check.setEnabled(enabled)
        if enabled:
            self.start_date_edit.setEnabled(self.date_filter_check.isChecked())
            self.end_date_edit.setEnabled(self.date_filter_check.isChecked())
        else:
            self.start_date_edit.setEnabled(False)
            self.end_date_edit.setEnabled(False)
        self.prev_btn.setEnabled(enabled and self._current_page > 1)
        self.next_btn.setEnabled(enabled and self._current_page < self._total_pages)

    def _on_loaded(self, result):
        self._set_controls_enabled(True)

        if result is None:
            self.table.setRowCount(0)
            self.total_label.setText("无法加载处理记录")
            self.total_label.setStyleSheet("color: #FF4444; font-size: 13px;")
            return

        if result.get("code") != 0:
            self.table.setRowCount(0)
            self.total_label.setText(result.get("message", "加载失败"))
            self.total_label.setStyleSheet("color: #FF4444; font-size: 13px;")
            return

        total = result.get("total", 0)
        self._records = result.get("data", []) or []
        self._total_pages = max(1, (total + self._page_size - 1) // self._page_size)

        self.total_label.setText(f"共 {total} 条记录")
        self.total_label.setStyleSheet("color: #8A94A6; font-size: 13px;")
        self.page_label.setText(f"第 {self._current_page} / {self._total_pages} 页")

        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            # 处理时间
            time_text = _format_datetime(record.get("created_at"))
            self.table.setItem(row, 0, QTableWidgetItem(time_text))

            # 操作类型（带配色徽章）
            action = record.get("action", "")
            self.table.setCellWidget(row, 1, ActionBadge(action))

            # 工单编号
            self.table.setItem(row, 2, QTableWidgetItem(record.get("ticket_id", "-")))

            # 客户 / 问题分类
            customer = record.get("ticket_customer_name") or "-"
            category = record.get("ticket_issue_category", "")
            category_text = CATEGORY_MAP.get(category, category or "-")
            self.table.setItem(row, 3, QTableWidgetItem(f"{customer} / {category_text}"))

        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 36)

    # ===== 点击行 → 显示详情 =====

    def _on_row_clicked(self, row, col):
        if row < 0 or row >= len(self._records):
            return
        self._selected_record = self._records[row]

        # 先用记录自身数据展示变更详情
        self._show_change_detail(self._selected_record)

        # 再异步加载工单完整详情
        ticket_id = self._selected_record.get("ticket_id")
        if ticket_id:
            if self._detail_thread and self._detail_thread.isRunning():
                try:
                    self._detail_thread.finished.disconnect()
                except Exception:
                    pass
            self._detail_thread = TicketDetailThread(self.api_client, ticket_id)
            self._detail_thread.finished.connect(self._on_detail_loaded)
            self._detail_thread.start()

    def _on_detail_loaded(self, result):
        """工单完整详情加载完成"""
        if result and result.get("code") == 0:
            data = result.get("data")
            if data:
                self._selected_ticket_detail = data
                self._show_ticket_detail(data)

    def _show_change_detail(self, record):
        """展示变更详情（使用记录自身数据，无需异步加载）"""
        self.detail_hint.setVisible(False)
        self.detail_change.setVisible(True)

        # 操作类型（ActionBadge）
        action = record.get("action", "")
        old_action = self.d_action
        self.d_action = ActionBadge(action)
        parent_layout = old_action.parent().layout()
        if parent_layout:
            parent_layout.replaceWidget(old_action, self.d_action)
            old_action.deleteLater()

        # 变更摘要（中文翻译）
        summary = _translate_summary(record.get("change_summary") or "-")
        self.d_summary.setText(summary)

        # 变更原因
        reason = record.get("reason") or "-"
        self.d_reason.setPlainText(reason)

        # 操作人
        operator = record.get("operator_username") or "-"
        self.d_operator.setText(operator)

        # 操作时间
        self.d_time.setText(_format_datetime(record.get("created_at")))

    def _show_ticket_detail(self, ticket):
        """展示工单完整详情（异步加载后填充）"""
        self.detail_overview.setVisible(True)
        self.detail_customer.setVisible(True)
        self.detail_assessment.setVisible(True)
        self.detail_extracted.setVisible(True)

        # 工单编号
        self.d_ticket_id.setText(ticket.get("ticket_id", "-"))

        # 状态（StatusBadge）
        status = ticket.get("status", "-")
        old_s = self.d_status
        self.d_status = StatusBadge(status)
        parent_layout_s = old_s.parent().layout()
        if parent_layout_s:
            parent_layout_s.replaceWidget(old_s, self.d_status)
            old_s.deleteLater()

        # 紧急度（UrgencyBadge）
        urgency = ticket.get("urgency_level", "")
        old_u = self.d_urgency
        self.d_urgency = UrgencyBadge(urgency)
        parent_layout_u = old_u.parent().layout()
        if parent_layout_u:
            parent_layout_u.replaceWidget(old_u, self.d_urgency)
            old_u.deleteLater()

        # 创建时间
        self.d_created.setText(_format_datetime(ticket.get("created_at")))

        # 解决时间
        self.d_resolved.setText(_format_datetime(ticket.get("resolved_at")))

        # 客户信息
        self.d_name.setText(ticket.get("customer_name") or "-")
        self.d_phone.setText(ticket.get("customer_phone") or "-")

        # 业务评估
        assessment = ticket.get("agent_business_assessment") or {}
        self.d_category.setText(
            CATEGORY_MAP.get(assessment.get("issue_category"), assessment.get("issue_category") or "-")
        )
        self.d_impact.setText(
            IMPACT_MAP.get(assessment.get("business_impact"), assessment.get("business_impact") or "-")
        )
        self.d_warranty.setText(
            WARRANTY_MAP.get(assessment.get("warranty_status"), assessment.get("warranty_status") or "-")
        )

        # 提取数据
        extracted = ticket.get("extracted_data") or {}
        self.d_order.setText(extracted.get("order_id") or "-")
        self.d_model.setText(extracted.get("model_number") or "-")
        self.d_batch.setText(extracted.get("batch_code") or "-")
        self.d_fault.setPlainText(extracted.get("core_fault_desc") or "-")

    # ===== 交互 =====

    def _on_search(self):
        self._current_page = 1
        self._load()

    def _on_reset(self):
        self.date_filter_check.setChecked(False)
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.end_date_edit.setDate(QDate.currentDate())
        self._current_page = 1
        self._load()

    def _on_refresh(self):
        self._load()

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load()

    def _on_next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load()
