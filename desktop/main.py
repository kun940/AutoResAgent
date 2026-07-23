import sys
import os
import shutil
import tempfile
import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QSizePolicy,
    QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from desktop.api_client import ApiClient
from desktop.views.login_view import LoginWindow
from desktop.views.dashboard_view import DashboardView
from desktop.views.submit_complaint_view import SubmitComplaintView
from desktop.views.ticket_list_view import TicketListView
from desktop.views.quality_analysis_view import QualityAnalysisView
from desktop.views.settings_view import SettingsView
from desktop.views.processing_records_view import ProcessingRecordsView


class HealthCheckThread(QThread):
    result_ready = pyqtSignal(bool)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client

    def run(self):
        is_healthy = self.api_client.check_health()
        self.result_ready.emit(is_healthy)


class NewTicketCheckThread(QThread):
    """新工单轮询线程"""
    result_ready = pyqtSignal(object)  # 返回新工单列表或None

    def __init__(self, api_client, since=None):
        super().__init__()
        self.api_client = api_client
        self.since = since

    def run(self):
        try:
            result = self.api_client.get_tickets(
                status="pending",
                page=1,
                page_size=5
            )
            if result and result.get("total", 0) > 0:
                self.result_ready.emit(result)
            else:
                self.result_ready.emit(None)
        except Exception:
            self.result_ready.emit(None)


# 导航图标（Unicode 字符，兼容纯文本 QPushButton）
NAV_ICONS = {
    0: "▦",   # 主看板 - 九宫格
    1: "✎",   # 提交客诉 - 编辑
    2: "☰",   # 工单列表 - 列表
    3: "▣",   # 质量分析 - 图表块
    4: "⚙",   # 系统设置 - 齿轮
    5: "📋",   # 处理记录 - 历史记录
}

NAV_NAMES = ["主看板", "提交客诉", "工单列表", "质量分析", "系统设置", "处理记录"]


class IconLabel(QWidget):
    """带 SVG 图标的标签按钮"""
    def __init__(self, svg_content, text="", badge_count=0, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_button")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        icon_widget = QLabel()
        icon_widget.setFixedSize(20, 20)
        icon_widget.setStyleSheet("background: transparent; border: none;")
        icon_widget.setTextFormat(Qt.TextFormat.RichText)
        icon_widget.setText(f'<span style="color: inherit;">{svg_content}</span>')
        layout.addWidget(icon_widget)

        text_label = QLabel(text)
        text_label.setStyleSheet("background: transparent; border: none; color: inherit;")
        layout.addWidget(text_label)

        if badge_count > 0:
            badge = QPushButton(str(badge_count))
            badge.setObjectName("nav_badge")
            badge.setEnabled(False)
            badge.setFixedHeight(18)
            layout.addWidget(badge)

        layout.addStretch()


# 角色可见页面配置：角色 -> 允许的页面索引列表
# v2.1 页面索引：0=主看板, 1=提交客诉, 2=工单列表, 3=质量分析, 4=系统设置, 5=处理记录
ROLE_NAV_MAP = {
    "frontline_staff": [0, 1, 2, 5],              # 主看板、提交客诉、工单列表、处理记录
    "department_manager": [0, 1, 2, 3, 5],        # 主看板、提交客诉、工单列表、质量分析、处理记录
    "general_manager": [0, 1, 2, 3, 4, 5],       # 全部页面
    "admin": [0, 1, 2, 3, 4, 5],                  # 全部页面
}


class SidebarWidget(QWidget):
    nav_clicked = pyqtSignal(int)
    logout_clicked = pyqtSignal()

    def __init__(self, role=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self._buttons = []
        self._current_index = -1
        self._role = role or "frontline_staff"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 品牌区
        title_label = QLabel("客诉管理工单台")
        title_label.setObjectName("sidebar_title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title_label)

        subtitle_label = QLabel("Customer Complaint System")
        subtitle_label.setObjectName("sidebar_subtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(subtitle_label)

        layout.addSpacing(8)

        all_nav_items = list(enumerate(NAV_NAMES))
        allowed = ROLE_NAV_MAP.get(self._role, [1, 2])
        self._nav_index_map = []  # 按钮索引 -> 原始页面索引

        # 工单列表的 badge（待处理数量占位）
        self._pending_badge = None

        for index, name in all_nav_items:
            if index not in allowed:
                continue
            btn = QPushButton()
            btn.setObjectName("nav_button")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(44)

            icon = NAV_ICONS.get(index, "")
            btn.setText(f"  {icon}  {name}")

            btn_index = len(self._buttons)
            btn.clicked.connect(lambda checked, idx=btn_index: self._on_nav_clicked(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)
            self._nav_index_map.append(index)

        layout.addStretch()

        self.user_label = QLabel("")
        self.user_label.setObjectName("nav_button")
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_label.setStyleSheet(
            "color: #8A94A6; font-size: 11px; padding: 4px 20px; "
            "background: transparent; border: none;"
        )
        layout.addWidget(self.user_label)

        version_label = QLabel("v2.1.0")
        version_label.setObjectName("nav_button")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(
            "color: #8A94A6; font-size: 11px; padding: 12px; "
            "background: transparent; border: none;"
        )
        layout.addWidget(version_label)

        logout_btn = QPushButton()
        logout_btn.setObjectName("nav_button")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setText("  ⏏  退出登录")
        logout_btn.setStyleSheet(
            "QPushButton#nav_button { color: #8A94A6; border: none; text-align: left; "
            "padding: 10px 20px; font-size: 13px; background: transparent; }"
            "QPushButton#nav_button:hover { color: #A8423A; background-color: #262C34; }"
        )
        logout_btn.clicked.connect(self.logout_clicked.emit)
        layout.addWidget(logout_btn)

        self.select_nav(0)

    def _on_nav_clicked(self, btn_index):
        self.select_nav(btn_index)
        page_index = self._nav_index_map[btn_index]
        self.nav_clicked.emit(page_index)

    def select_nav(self, index):
        if self._current_index == index:
            return
        for i, btn in enumerate(self._buttons):
            btn.setProperty("selected", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._current_index = index


class MainWindow(QMainWindow):
    def __init__(self, api_client=None):
        super().__init__()
        self.setWindowTitle("客诉自动回复与质量追溯系统")
        self.resize(1200, 800)
        self._center_window()

        self.api_client = api_client or ApiClient()
        self._role = self.api_client.user_info.get("role", "frontline_staff") if self.api_client.user_info else "frontline_staff"
        self._is_quitting = False
        self._last_ticket_count = 0
        self._new_ticket_thread = None
        self._setup_ui()
        self._setup_tray_icon()
        self._check_backend_health()
        self._start_new_ticket_polling()

        if self.api_client.user_info:
            username = self.api_client.user_info.get("username", "")
            self.sidebar.user_label.setText(f"👤 {username}")

    def _center_window(self):
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = (geometry.width() - self.width()) // 2
            y = (geometry.height() - self.height()) // 2
            self.move(x, y)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = SidebarWidget(role=self._role)
        self.sidebar.nav_clicked.connect(self._switch_page)
        self.sidebar.logout_clicked.connect(self._on_logout)
        main_layout.addWidget(self.sidebar)

        # 右侧容器
        right_container = QWidget()
        right_container.setObjectName("content_area")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 后端警告
        self.warning_bar = QLabel()
        self.warning_bar.setObjectName("backend_warning")
        self.warning_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_bar.setText("⚠ 后端服务未连接，部分功能不可用。请确认后端服务已启动（http://localhost:8000）")
        self.warning_bar.setVisible(False)
        right_layout.addWidget(self.warning_bar)

        # 页面栈
        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")

        page_titles = ["主看板", "提交客诉", "工单列表", "质量分析", "系统设置", "处理记录"]
        from desktop.views.dashboard_view import PlaceholderPage
        for title in page_titles:
            page = PlaceholderPage(title)
            self.stack.addWidget(page)

        self.stack.removeWidget(self.stack.widget(0))
        self.stack.insertWidget(0, DashboardView(self.api_client, role=self._role))
        self.stack.removeWidget(self.stack.widget(1))
        self.stack.insertWidget(1, SubmitComplaintView(self.api_client))
        self.stack.removeWidget(self.stack.widget(2))
        self.stack.insertWidget(2, TicketListView(self.api_client, role=self._role))
        self.stack.removeWidget(self.stack.widget(3))
        self.stack.insertWidget(3, QualityAnalysisView(self.api_client, role=self._role))
        self.stack.removeWidget(self.stack.widget(4))
        self.stack.insertWidget(4, SettingsView(self.api_client))
        self.stack.removeWidget(self.stack.widget(5))
        self.stack.insertWidget(5, ProcessingRecordsView(self.api_client, role=self._role))

        right_layout.addWidget(self.stack)
        main_layout.addWidget(right_container)

    def _switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def _check_backend_health(self):
        self._health_thread = HealthCheckThread(self.api_client)
        self._health_thread.result_ready.connect(self._on_health_result)
        self._health_thread.start()

    def _on_health_result(self, is_healthy):
        self.warning_bar.setVisible(not is_healthy)

    def _on_logout(self):
        self.api_client.token = None
        self.api_client.user_info = None
        # 停止轮询
        if hasattr(self, '_poll_timer'):
            self._poll_timer.stop()
        # 隐藏托盘图标
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        login_window = LoginWindow(self.api_client)
        login_window.login_success.connect(lambda user_info: _on_login_success(login_window, self.api_client))
        login_window.show()
        self.close()

    def _setup_tray_icon(self):
        """设置系统托盘图标"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("客诉自动回复出单智能体")

        tray_menu = QMenu()

        show_action = tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self._show_normal)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self._quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_icon_activated)
        self.tray_icon.show()

    def _show_normal(self):
        self.showNormal()
        self.activateWindow()

    def _tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_normal()

    def _quit_app(self):
        self._is_quitting = True
        if hasattr(self, '_poll_timer'):
            self._poll_timer.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self._is_quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "客诉自动回复出单智能体",
            "程序已最小化到系统托盘，双击图标可恢复窗口",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def _start_new_ticket_polling(self):
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_new_tickets)
        self._poll_timer.start(30000)
        self._check_new_tickets()

    def _check_new_tickets(self):
        if self._new_ticket_thread and self._new_ticket_thread.isRunning():
            return
        self._new_ticket_thread = NewTicketCheckThread(self.api_client)
        self._new_ticket_thread.result_ready.connect(self._on_new_tickets_checked)
        self._new_ticket_thread.start()

    def _on_new_tickets_checked(self, result):
        if result is None:
            return

        total = result.get("total", 0)
        tickets = result.get("data", [])

        if self._last_ticket_count == 0:
            self._last_ticket_count = total
            return

        if total > self._last_ticket_count:
            new_count = total - self._last_ticket_count
            self._last_ticket_count = total

            if tickets:
                latest = tickets[0]
                ticket_id = latest.get("ticket_id", "-")
                urgency = latest.get("urgency_level", "")
                urgency_labels = {
                    "High_Priority": "高紧急",
                    "Medium_Priority": "中紧急",
                    "Low_Priority": "低紧急",
                }
                category = latest.get("issue_category", "")
                category_labels = {
                    "Missing_Parts": "配件缺失",
                    "Operation_Error": "操作错误",
                    "Software_Bug": "软件缺陷",
                    "Hardware_Malfunction": "硬件故障",
                    "Other": "其他",
                }

                urgency_text = urgency_labels.get(urgency, urgency or "")
                category_text = category_labels.get(category, category or "")

                message = f"您有 {new_count} 个新工单\n"
                message += f"最新：{ticket_id}\n"
                if urgency_text:
                    message += f"紧急度：{urgency_text}\n"
                if category_text:
                    message += f"分类：{category_text}"

                self.tray_icon.showMessage(
                    "新工单通知",
                    message,
                    QSystemTrayIcon.MessageIcon.Information,
                    5000
                )
            else:
                self.tray_icon.showMessage(
                    "新工单通知",
                    f"您有 {new_count} 个新工单待处理",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )


def load_stylesheet(app):
    qss_path = os.path.join(os.path.dirname(__file__), "resources", "styles", "main.qss")
    if os.path.isfile(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def cleanup_temp_images(max_age_hours=24):
    tmp_dir = os.path.join(tempfile.gettempdir(), "complaint_images")
    if not os.path.exists(tmp_dir):
        return
    now = time.time()
    for filename in os.listdir(tmp_dir):
        filepath = os.path.join(tmp_dir, filename)
        try:
            if os.path.isfile(filepath) and (now - os.path.getmtime(filepath)) > max_age_hours * 3600:
                os.remove(filepath)
        except Exception:
            pass


def cleanup_all_temp_images():
    tmp_dir = os.path.join(tempfile.gettempdir(), "complaint_images")
    if os.path.exists(tmp_dir):
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


def main():
    cleanup_temp_images()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.aboutToQuit.connect(cleanup_all_temp_images)

    load_stylesheet(app)

    api_client = ApiClient()

    login_window = LoginWindow(api_client)
    login_window.login_success.connect(lambda user_info: _on_login_success(login_window, api_client))
    login_window.show()

    sys.exit(app.exec())


def _on_login_success(login_window, api_client):
    try:
        window = MainWindow(api_client)
        window.show()
        # 保持主窗口引用，防止被垃圾回收
        app = QApplication.instance()
        app._main_window_ref = window
        # 延迟销毁登录窗口，确保主窗口已经完全显示并激活
        QTimer.singleShot(0, login_window.deleteLater)
    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(None, "启动失败", f"主窗口初始化失败：\n{e}")
        login_window.show()


if __name__ == "__main__":
    main()