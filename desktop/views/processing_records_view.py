from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDateEdit, QCheckBox, QFrame
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

STATUS_LABELS = {
    "pending": "待处理",
    "processing": "处理中",
    "routed": "已路由",
    "resolved": "已解决",
    "closed": "已关闭",
    "cancelled": "已取消",
}

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
        # 兼容已有 'YYYY-MM-DDTHH:MM' 截断展示
        text = str(value)
        if len(text) >= 16:
            return text[:16].replace("T", " ")
        return text


class ProcessingRecordsView(QWidget):
    """处理记录页面：展示当前账号的工单处理操作历史"""

    def __init__(self, api_client: ApiClient, role=None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._role = role
        self._current_page = 1
        self._total_pages = 1
        self._page_size = 20
        self._records = []
        self._load_thread = None
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

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "处理时间", "操作类型", "工单编号", "客户 / 分类", "变更摘要", "变更原因"
        ])
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 200)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.table, 1)

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

            # 客户 / 分类
            customer = record.get("ticket_customer_name") or "-"
            category = record.get("ticket_issue_category", "")
            category_text = CATEGORY_MAP.get(category, category or "-")
            self.table.setItem(row, 3, QTableWidgetItem(f"{customer} / {category_text}"))

            # 变更摘要
            self.table.setItem(row, 4, QTableWidgetItem(record.get("change_summary") or "-"))

            # 变更原因
            reason = record.get("reason") or "-"
            self.table.setItem(row, 5, QTableWidgetItem(reason))

        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 36)

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
