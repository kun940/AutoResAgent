from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget
)
from PyQt6.QtCore import Qt

from desktop.views.dashboard_view import (
    CollapsibleSection, URGENCY_LABELS, STATUS_LABELS
)


class SubordinateDetailDialog(QDialog):
    """下级工单处理详情对话框（v2.1.0 增量改动）

    在主看板"下级工单处理概览"区块点击"查看详情"后弹出，
    承载原本内联在看板中的折叠面板 + 待处理工单详情列表，
    使主看板只显示汇总数据，详情在新窗口中查看。
    """

    def __init__(self, sub_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下级工单处理详情")
        self.setMinimumSize(880, 560)
        self.setModal(False)
        self._sub_data = sub_data or []
        self._setup_ui()
        self._render_sections(self._sub_data)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # 顶部说明
        header = QHBoxLayout()
        title_label = QLabel("📋 下级工单处理详情")
        title_label.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #1E2329;"
        )
        header.addWidget(title_label)

        hint_label = QLabel("展开各角色面板可查看待处理工单明细，内容较多时可上下滚动")
        hint_label.setStyleSheet("font-size: 12px; color: #8A94A6;")
        hint_label.setContentsMargins(8, 0, 0, 0)
        header.addWidget(hint_label)
        header.addStretch()
        outer.addLayout(header)

        # 滚动容器：内容超出视口高度时自动出现垂直滚动条，支持大量工单浏览，不会爆满
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 8px; background: #F0F0F0; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #BDC3C7; border-radius: 4px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar:horizontal { height: 8px; background: #F0F0F0; border-radius: 4px; }"
            "QScrollBar::handle:horizontal { background: #BDC3C7; border-radius: 4px; min-width: 30px; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
        )

        self.container = QWidget()
        # 设置最小宽度，确保工单行（工单ID/客户名/紧急度/状态/时间）即使窗口被缩小也不会被压缩重叠
        self.container.setMinimumWidth(620)
        self.sections_layout = QVBoxLayout(self.container)
        self.sections_layout.setSpacing(12)
        self.sections_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll.setWidget(self.container)
        outer.addWidget(self.scroll, 1)

        # 空态占位
        self.empty_label = QLabel("暂无下级工单数据")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #BDC3C7; font-size: 14px; padding: 40px;")
        self.empty_label.setVisible(False)
        outer.addWidget(self.empty_label)

        # 底部操作区
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setProperty("secondary", True)
        close_btn.setFixedSize(96, 34)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

    def _render_sections(self, sub_data):
        if not sub_data:
            self.empty_label.setVisible(True)
            self.scroll.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.scroll.setVisible(True)

        for item in sub_data:
            role_display = item.get("role_display", item.get("role", "未知"))
            total = item.get("total_count", 0)
            pending = item.get("pending_count", 0)
            resolved = item.get("resolved_count", 0)
            pending_tickets = item.get("pending_tickets", [])

            section_title = f"{role_display}  —  总计 {total} | 待处理 {pending} | 已解决 {resolved}"
            section = CollapsibleSection(section_title)

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
                    customer_label.setFixedWidth(80)
                    customer_label.setStyleSheet("font-size: 12px; color: #2C3E50;")
                    row.addWidget(customer_label)

                    urgency = t.get("urgency_level", "")
                    urgency_text = URGENCY_LABELS.get(urgency, urgency or "-")
                    urgency_color = {
                        "High_Priority": "#FF4444",
                        "Medium_Priority": "#FF9800",
                        "Low_Priority": "#4CAF50",
                    }.get(urgency, "#95A5A6")
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

            self.sections_layout.addWidget(section)

        # 末尾弹簧，避免内容偏上
        self.sections_layout.addStretch()
