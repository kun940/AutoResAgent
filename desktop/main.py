import sys
import os
import shutil
import tempfile
import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QSizePolicy,
    QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from desktop.api_client import ApiClient
from desktop.views.login_view import LoginWindow
from desktop.views.dashboard_view import DashboardView
from desktop.views.submit_complaint_view import SubmitComplaintView
from desktop.views.ticket_list_view import TicketListView
from desktop.views.order_manage_view import OrderManageView
from desktop.views.quality_analysis_view import QualityAnalysisView
from desktop.views.settings_view import SettingsView


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


class NavButton(QPushButton):
    def __init__(self, text, icon_char="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("nav_button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)
        self._icon_char = icon_char
        if icon_char:
            self.setText(f"  {icon_char}  {text}")
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


# 角色可见页面配置：角色 -> 允许的页面索引列表
# 页面索引：0=主看板, 1=提交客诉, 2=工单列表, 3=出单管理, 4=质量分析, 5=系统设置
ROLE_NAV_MAP = {
    "frontline_staff": [0, 1, 2, 3],             # 主看板、提交客诉、工单列表、出单管理
    "department_manager": [0, 1, 2, 3, 4],        # 主看板、提交客诉、工单列表、出单管理、质量分析
    "general_manager": [0, 1, 2, 3, 4, 5],       # 全部页面
    "admin": [0, 1, 2, 3, 4, 5],                  # 全部页面
}


class SidebarWidget(QWidget):
    nav_clicked = pyqtSignal(int)
    logout_clicked = pyqtSignal()

    def __init__(self, role=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)
        self._buttons = []
        self._current_index = -1
        self._role = role or "frontline_staff"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_label = QLabel("客诉管理工单台")
        title_label.setObjectName("sidebar_title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #34495E; max-height: 1px; border: none;")
        layout.addWidget(separator)

        layout.addSpacing(12)

        all_nav_items = [
            ("主看板", "\U0001F4CA"),
            ("提交客诉", "\U0001F4E4"),
            ("工单列表", "\U0001F4CB"),
            ("出单管理", "\U0001F4E6"),
            ("质量分析", "\U0001F52C"),
            ("系统设置", "\u2699\uFE0F"),
        ]

        allowed = ROLE_NAV_MAP.get(self._role, [1, 2])
        self._nav_index_map = []  # 按钮索引 -> 原始页面索引

        for index, (text, icon) in enumerate(all_nav_items):
            if index not in allowed:
                continue
            btn = NavButton(text, icon)
            btn_index = len(self._buttons)
            btn.clicked.connect(lambda checked, idx=btn_index: self._on_nav_clicked(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)
            self._nav_index_map.append(index)

        layout.addStretch()

        self.user_label = QLabel("")
        self.user_label.setObjectName("nav_button")
        self.user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_label.setStyleSheet("color: #7F8C8D; font-size: 11px; padding: 4px 12px;")
        layout.addWidget(self.user_label)

        version_label = QLabel("v1.0.0")
        version_label.setObjectName("nav_button")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #7F8C8D; font-size: 11px; padding: 12px;")
        layout.addWidget(version_label)

        logout_btn = QPushButton("  🚪  退出登录")
        logout_btn.setObjectName("nav_button")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            "QPushButton { color: #E74C3C; border: none; text-align: left; "
            "padding: 10px 20px; font-size: 13px; }"
            "QPushButton:hover { background-color: #3D4F5F; }"
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


class PlaceholderPage(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("content_area")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f"📋 {title}\n\n页面开发中...")
        label.setObjectName("page_label")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        label.setFont(font)
        layout.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self, api_client=None):
        super().__init__()
        self.setWindowTitle("客诉自动回复出单智能体")
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

        self.sidebar = SidebarWidget(role=self._role)
        self.sidebar.nav_clicked.connect(self._switch_page)
        self.sidebar.logout_clicked.connect(self._on_logout)
        main_layout.addWidget(self.sidebar)

        right_container = QWidget()
        right_container.setObjectName("content_area")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.warning_bar = QLabel()
        self.warning_bar.setObjectName("backend_warning")
        self.warning_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_bar.setText("⚠ 后端服务未连接，部分功能不可用。请确认后端服务已启动（http://localhost:8000）")
        self.warning_bar.setVisible(False)
        right_layout.addWidget(self.warning_bar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")

        page_titles = ["主看板", "提交客诉", "工单列表", "出单管理", "质量分析", "系统设置"]
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
        self.stack.insertWidget(3, OrderManageView(self.api_client, role=self._role))
        self.stack.removeWidget(self.stack.widget(4))
        self.stack.insertWidget(4, QualityAnalysisView(self.api_client, role=self._role))
        self.stack.removeWidget(self.stack.widget(5))
        self.stack.insertWidget(5, SettingsView(self.api_client))

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
        # 使用系统标准图标
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("客诉自动回复出单智能体")

        # 托盘菜单
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
        """从托盘恢复主窗口"""
        self.showNormal()
        self.activateWindow()

    def _tray_icon_activated(self, reason):
        """托盘图标激活事件"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_normal()

    def _quit_app(self):
        """真正退出应用"""
        self._is_quitting = True
        if hasattr(self, '_poll_timer'):
            self._poll_timer.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """关闭时最小化到托盘而非退出"""
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
        """启动新工单轮询定时器（每30秒）"""
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_new_tickets)
        self._poll_timer.start(30000)  # 30秒
        # 首次立即检查
        self._check_new_tickets()

    def _check_new_tickets(self):
        """检查是否有新工单"""
        if self._new_ticket_thread and self._new_ticket_thread.isRunning():
            return
        self._new_ticket_thread = NewTicketCheckThread(self.api_client)
        self._new_ticket_thread.result_ready.connect(self._on_new_tickets_checked)
        self._new_ticket_thread.start()

    def _on_new_tickets_checked(self, result):
        """新工单检查结果回调"""
        if result is None:
            return

        total = result.get("total", 0)
        tickets = result.get("data", [])

        # 首次加载只记录数量，不弹通知
        if self._last_ticket_count == 0:
            self._last_ticket_count = total
            return

        # 有新增工单
        if total > self._last_ticket_count:
            new_count = total - self._last_ticket_count
            self._last_ticket_count = total

            # 通过系统托盘弹出通知
            if tickets:
                # 取最新的一条工单信息
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
    window = MainWindow(api_client)
    window.show()
    # 保持引用防止Python垃圾回收导致窗口被销毁
    QApplication.instance()._main_window_ref = window
    login_window.deleteLater()


if __name__ == "__main__":
    main()
