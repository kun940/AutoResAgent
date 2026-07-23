from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QProgressBar, QSizePolicy, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QParallelAnimationGroup, QPropertyAnimation
from PyQt6.QtGui import QFont, QColor

from desktop.api_client import ApiClient


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

ROLE_HIERARCHY = ["frontline_staff", "department_manager", "general_manager"]


class PlaceholderPage(QWidget):
    """页面占位组件（仅在 MainWindow 初始化时使用，随后会被实际视图替换）"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px; color: #8A94A6;")
        layout.addWidget(label)
        layout.addStretch()


class CollapsibleSection(QWidget):
    """可折叠的区域组件"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._expanded = True
        self._title = title

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 标题按钮
        self.toggle_btn = QPushButton(f"  ▼  {title}")
        self.toggle_btn.setStyleSheet(
            "QPushButton { background-color: #F0F2F5; border: 1px solid #EAEDF2; "
            "border-radius: 6px; padding: 8px 12px; font-size: 14px; font-weight: 600; "
            "color: #1E2329; text-align: left; }"
            "QPushButton:hover { background-color: #E8EAEE; }"
        )
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)
        outer_layout.addWidget(self.toggle_btn)

        # 内容区域
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(4)
        self.content_area.setStyleSheet("border: 1px solid #EAEDF2; border-top: none; border-radius: 0 0 6px 6px; background-color: #FFFFFF;")
        outer_layout.addWidget(self.content_area)

    def _toggle(self):
        self._expanded = not self._expanded
        self.content_area.setVisible(self._expanded)
        arrow = "  ▼" if self._expanded else "  ▶"
        self.toggle_btn.setText(f"{arrow}  {self._title}")

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


class DashboardLoadThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, target_role=None):
        super().__init__()
        self.api_client = api_client
        self.target_role = target_role

    def run(self):
        result = self.api_client.get_dashboard_stats(target_role=self.target_role)
        self.finished.emit(result)


class SubordinateLoadThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, role):
        super().__init__()
        self.api_client = api_client
        self.role = role

    def run(self):
        result = self.api_client.get_subordinate_overview(role=self.role)
        self.finished.emit(result)


class QualityDashboardLoadThread(QThread):
    """质量看板数据加载线程（v1.2: 出单统计已移除，保留线程供后续扩展）"""
    finished = pyqtSignal(object)

    def __init__(self, api_client, target_role=None):
        super().__init__()
        self.api_client = api_client
        self.target_role = target_role

    def run(self):
        result = self.api_client.get_dashboard_quality(target_role=self.target_role)
        self.finished.emit(result)


class StatCard(QWidget):
    def __init__(self, icon, title, value="0", color="#1E2329", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background-color: #FFFFFF; border: 1px solid #EAEDF2; "
            "border-radius: 10px; }"
        )
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 22px; border: none; background: transparent;")
        top_row.addWidget(icon_label)

        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(
            f"font-size: 26px; font-weight: 600; color: {color}; "
            "border: none; background: transparent; font-family: 'JetBrains Mono', 'Consolas', monospace;"
        )
        top_row.addStretch()
        top_row.addWidget(self.value_label)
        layout.addLayout(top_row)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 13px; color: #8A94A6; border: none; background: transparent;"
        )
        layout.addWidget(self.title_label)

    def set_value(self, value):
        self.value_label.setText(str(value))


class DashboardView(QWidget):
    def __init__(self, api_client: ApiClient, role=None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._role = role
        self._load_thread = None
        self._sub_thread = None
        self._quality_thread = None
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        title = QLabel("主看板")
        title.setObjectName("page_title")
        header_layout.addWidget(title)

        subtitle = QLabel("欢迎回来，以下是今日数据概览")
        subtitle.setObjectName("page_subtitle")
        subtitle.setContentsMargins(8, 0, 0, 0)
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setProperty("secondary", True)
        self.refresh_btn.setFixedSize(80, 36)
        self.refresh_btn.clicked.connect(self._load_data)
        header_layout.addWidget(self.refresh_btn)
        main_layout.addLayout(header_layout)

        self.loading_label = QLabel("加载中...")
        self.loading_label.setStyleSheet("color: #C9A86A; font-size: 14px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setVisible(False)
        main_layout.addWidget(self.loading_label)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.card_total = StatCard("📊", "工单总数", "0", "#1E2329")
        self.card_pending = StatCard("⏳", "待处理", "0", "#C77D3C")
        self.card_high = StatCard("🔥", "高紧急", "0", "#A8423A")
        self.card_overdue = StatCard("⚠️", "已超时(SLA)", "0", "#A8423A")

        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_pending)
        cards_layout.addWidget(self.card_high)
        cards_layout.addWidget(self.card_overdue)
        main_layout.addLayout(cards_layout)

        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(16)

        self.category_group = QGroupBox("问题分类分布")
        self.category_layout = QVBoxLayout(self.category_group)
        self.category_layout.setSpacing(8)
        mid_layout.addWidget(self.category_group)

        self.trend_group = QGroupBox("近7日工单趋势")
        self.trend_layout = QVBoxLayout(self.trend_group)
        self.trend_layout.setSpacing(8)
        mid_layout.addWidget(self.trend_group)

        main_layout.addLayout(mid_layout, 3)

        self.overdue_group = QGroupBox("⚠ 超时预警")
        self.overdue_layout = QVBoxLayout(self.overdue_group)
        self.overdue_label = QLabel("暂无超时工单")
        self.overdue_label.setStyleSheet("color: #7F8C8D; font-size: 13px; padding: 8px;")
        self.overdue_layout.addWidget(self.overdue_label)
        main_layout.addWidget(self.overdue_group)

        # 下级工单概览区域（仅高级别角色显示）
        self.subordinate_group = QGroupBox("📋 下级工单处理概览")
        subordinate_outer = QVBoxLayout(self.subordinate_group)
        subordinate_outer.setContentsMargins(0, 0, 0, 0)
        subordinate_outer.setSpacing(0)

        self.subordinate_scroll = QScrollArea()
        self.subordinate_scroll.setWidgetResizable(True)
        self.subordinate_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.subordinate_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 8px; background: #F0F0F0; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #BDC3C7; border-radius: 4px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        self.subordinate_container = QWidget()
        self.subordinate_layout = QVBoxLayout(self.subordinate_container)
        self.subordinate_layout.setSpacing(12)
        self.subordinate_layout.setContentsMargins(8, 8, 8, 8)
        self.subordinate_scroll.setWidget(self.subordinate_container)

        subordinate_outer.addWidget(self.subordinate_scroll)
        self.subordinate_group.setVisible(False)
        main_layout.addWidget(self.subordinate_group, 2)

    def _has_subordinates(self):
        """当前角色是否有下级"""
        if not self._role:
            return False
        try:
            idx = ROLE_HIERARCHY.index(self._role)
            return idx > 0
        except ValueError:
            return False

    def _load_data(self):
        self.loading_label.setVisible(True)
        self.refresh_btn.setEnabled(False)

        self._load_thread = DashboardLoadThread(self.api_client, target_role=self._role)
        self._load_thread.finished.connect(self._on_data_loaded)
        self._load_thread.start()

        if self._has_subordinates():
            self._sub_thread = SubordinateLoadThread(self.api_client, self._role)
            self._sub_thread.finished.connect(self._on_subordinate_loaded)
            self._sub_thread.start()

    def _on_data_loaded(self, result):
        self.loading_label.setVisible(False)
        self.refresh_btn.setEnabled(True)

        if result is None:
            self.loading_label.setText("无法加载看板数据，请检查后端服务")
            self.loading_label.setStyleSheet("color: #FF4444; font-size: 14px;")
            self.loading_label.setVisible(True)
            return

        data = result.get("data", {}) if isinstance(result, dict) else {}
        self._update_cards(data)
        self._update_category(data)
        self._update_trend(data)
        self._update_overdue(data)

    def _on_subordinate_loaded(self, result):
        if result is None or result.get("code") != 0:
            self.subordinate_group.setVisible(False)
            return

        sub_data = result.get("data", [])
        if not sub_data:
            self.subordinate_group.setVisible(False)
            return

        self.subordinate_group.setVisible(True)
        self._clear_layout(self.subordinate_layout)

        for item in sub_data:
            role_display = item.get("role_display", item.get("role", "未知"))
            total = item.get("total_count", 0)
            pending = item.get("pending_count", 0)
            resolved = item.get("resolved_count", 0)
            pending_tickets = item.get("pending_tickets", [])

            section_title = f"{role_display}  —  总计 {total} | 待处理 {pending} | 已解决 {resolved}"
            section = CollapsibleSection(section_title)

            # 待处理工单详情
            if pending_tickets:
                for t in pending_tickets:
                    row = QHBoxLayout()
                    row.setSpacing(8)

                    tid = t.get("ticket_id", "-")
                    tid_label = QLabel(tid)
                    tid_label.setFixedWidth(140)
                    tid_label.setStyleSheet("font-size: 12px; color: #3498DB; font-weight: bold;")
                    row.addWidget(tid_label)

                    customer = t.get("customer_name", "未知")
                    customer_label = QLabel(customer)
                    customer_label.setFixedWidth(60)
                    customer_label.setStyleSheet("font-size: 12px; color: #2C3E50;")
                    row.addWidget(customer_label)

                    urgency = t.get("urgency_level", "")
                    urgency_text = URGENCY_LABELS.get(urgency, urgency or "-")
                    urgency_color = {"High_Priority": "#FF4444", "Medium_Priority": "#FF9800", "Low_Priority": "#4CAF50"}.get(urgency, "#95A5A6")
                    urgency_label = QLabel(f"  {urgency_text}  ")
                    urgency_label.setStyleSheet(
                        f"background-color: {urgency_color}; color: #FFFFFF; "
                        f"border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
                    )
                    urgency_label.setFixedHeight(22)
                    row.addWidget(urgency_label)

                    status = t.get("status", "")
                    status_text = STATUS_LABELS.get(status, status or "-")
                    status_label = QLabel(f"  {status_text}  ")
                    status_label.setStyleSheet(
                        "background-color: #D6EAF8; color: #2471A3; "
                        "border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
                    )
                    status_label.setFixedHeight(22)
                    row.addWidget(status_label)

                    created = t.get("created_at", "-")
                    if created and len(created) >= 16:
                        created = created[:16].replace("T", " ")
                    time_label = QLabel(created)
                    time_label.setStyleSheet("font-size: 12px; color: #7F8C8D;")
                    row.addWidget(time_label)

                    row.addStretch()
                    section.add_layout(row)
            else:
                no_pending = QLabel("暂无待处理工单")
                no_pending.setStyleSheet("font-size: 12px; color: #BDC3C7; padding: 4px 0;")
                section.add_widget(no_pending)

            self.subordinate_layout.addWidget(section)

    def _update_cards(self, data):
        self.card_total.set_value(data.get("total_tickets", 0))
        self.card_pending.set_value(data.get("pending_count", 0))
        self.card_high.set_value(data.get("high_priority_count", 0))
        self.card_overdue.set_value(data.get("overdue_count", 0))

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            sub_layout = item.layout()
            if sub_layout:
                self._clear_layout(sub_layout)

    def _update_category(self, data):
        self._clear_layout(self.category_layout)
        distribution = data.get("category_distribution", {})
        total = data.get("total_tickets", 1) or 1

        if not distribution:
            label = QLabel("暂无分类数据")
            label.setStyleSheet("color: #BDC3C7; font-size: 13px;")
            self.category_layout.addWidget(label)
            return

        for key, count in distribution.items():
            row = QHBoxLayout()
            row.setSpacing(8)

            name = CATEGORY_MAP.get(key, key)
            name_label = QLabel(name)
            name_label.setFixedWidth(80)
            name_label.setStyleSheet("font-size: 13px; color: #1E2329;")
            row.addWidget(name_label)

            bar = QProgressBar()
            bar.setRange(0, total)
            bar.setValue(count)
            bar.setTextVisible(False)
            bar.setFixedHeight(18)
            bar.setStyleSheet(
                "QProgressBar { background-color: #F0F2F5; border: none; border-radius: 9px; }"
                "QProgressBar::chunk { background-color: #C9A86A; border-radius: 9px; }"
            )
            row.addWidget(bar, 1)

            count_label = QLabel(str(count))
            count_label.setFixedWidth(40)
            count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            count_label.setStyleSheet("font-size: 13px; color: #1E2329; font-weight: 600;")
            row.addWidget(count_label)

            self.category_layout.addLayout(row)

    def _update_trend(self, data):
        self._clear_layout(self.trend_layout)
        daily = data.get("daily_trend", {})

        if not daily:
            label = QLabel("暂无趋势数据")
            label.setStyleSheet("color: #BDC3C7; font-size: 13px;")
            self.trend_layout.addWidget(label)
            return

        max_val = max(daily.values()) if daily else 1
        max_val = max(max_val, 1)

        for date_str, count in daily.items():
            row = QHBoxLayout()
            row.setSpacing(8)

            parts = date_str.split("-")
            if len(parts) == 3:
                display_date = f"{parts[1]}-{parts[2]}"
            else:
                display_date = date_str

            date_label = QLabel(display_date)
            date_label.setFixedWidth(60)
            date_label.setStyleSheet("font-size: 13px; color: #1E2329;")
            row.addWidget(date_label)

            bar = QProgressBar()
            bar.setRange(0, max_val)
            bar.setValue(count)
            bar.setTextVisible(False)
            bar.setFixedHeight(18)
            bar.setStyleSheet(
                "QProgressBar { background-color: #F0F2F5; border: none; border-radius: 9px; }"
                "QProgressBar::chunk { background-color: #C9A86A; border-radius: 9px; }"
            )
            row.addWidget(bar, 1)

            count_label = QLabel(str(count))
            count_label.setFixedWidth(40)
            count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            count_label.setStyleSheet("font-size: 13px; color: #1E2329; font-weight: 600;")
            row.addWidget(count_label)

            self.trend_layout.addLayout(row)

    def _update_overdue(self, data):
        overdue_count = data.get("overdue_count", 0)
        if overdue_count > 0:
            self.overdue_label.setText(
                f"当前有 {overdue_count} 个工单超过SLA时限，请在工单列表中查看详情"
            )
            self.overdue_label.setStyleSheet("color: #A8423A; font-size: 13px; padding: 8px; font-weight: 600;")
        else:
            self.overdue_label.setText("暂无超时工单")
            self.overdue_label.setStyleSheet("color: #8A94A6; font-size: 13px; padding: 8px;")
