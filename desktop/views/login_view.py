from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QStackedWidget, QGroupBox,
    QFormLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from desktop.api_client import ApiClient


class LoginThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, username, password):
        super().__init__()
        self.api_client = api_client
        self.username = username
        self.password = password

    def run(self):
        result = self.api_client.login(self.username, self.password)
        self.finished.emit(result)


class RegisterThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, api_client, username, password, role):
        super().__init__()
        self.api_client = api_client
        self.username = username
        self.password = password
        self.role = role

    def run(self):
        result = self.api_client.register(self.username, self.password, self.role)
        self.finished.emit(result)


class LoginWindow(QMainWindow):
    login_success = pyqtSignal(dict)

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._login_thread = None
        self._register_thread = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("客诉自动回复出单智能体 - 登录")
        self.setFixedSize(440, 520)
        self._center_window()

        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background-color: #F5F6FA;")

        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(40, 40, 40, 40)
        outer_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_login_page())
        self.stack.addWidget(self._build_register_page())
        outer_layout.addWidget(self.stack)

    def _center_window(self):
        screen = self.screen()
        if screen:
            geometry = screen.availableGeometry()
            x = (geometry.width() - self.width()) // 2
            y = (geometry.height() - self.height()) // 2
            self.move(x, y)

    def _build_login_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addSpacing(20)

        app_name = QLabel("客诉自动回复出单智能体")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setStyleSheet("font-size: 22px; font-weight: bold; color: #2C3E50; background: transparent;")
        layout.addWidget(app_name)

        subtitle = QLabel("智能客诉处理平台")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #7F8C8D; margin-top: 8px; background: transparent;")
        layout.addWidget(subtitle)

        layout.addSpacing(30)

        form_group = QGroupBox()
        form_group.setStyleSheet(
            "QGroupBox { background-color: #FFFFFF; border: 1px solid #E0E0E0; "
            "border-radius: 8px; padding: 24px 20px; margin-top: 0; }"
        )
        form_layout = QVBoxLayout(form_group)
        form_layout.setSpacing(16)

        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("用户名")
        self.login_username.setFixedHeight(40)
        self.login_username.setStyleSheet(
            "QLineEdit { border: 1px solid #DDD; border-radius: 4px; "
            "padding: 8px 12px; font-size: 14px; }"
            "QLineEdit:focus { border: 1px solid #3498DB; }"
        )
        form_layout.addWidget(self.login_username)

        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("密码")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.setFixedHeight(40)
        self.login_password.setStyleSheet(
            "QLineEdit { border: 1px solid #DDD; border-radius: 4px; "
            "padding: 8px 12px; font-size: 14px; }"
            "QLineEdit:focus { border: 1px solid #3498DB; }"
        )
        self.login_password.returnPressed.connect(self._on_login)
        form_layout.addWidget(self.login_password)

        self.login_btn = QPushButton("登 录")
        self.login_btn.setFixedHeight(44)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet(
            "QPushButton { background-color: #3498DB; color: #FFFFFF; border: none; "
            "border-radius: 4px; font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #2980B9; }"
            "QPushButton:disabled { background-color: #BDC3C7; }"
        )
        self.login_btn.clicked.connect(self._on_login)
        form_layout.addWidget(self.login_btn)

        self.login_error = QLabel("")
        self.login_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_error.setStyleSheet("color: #FF4444; font-size: 13px; background: transparent;")
        self.login_error.setFixedHeight(20)
        form_layout.addWidget(self.login_error)

        layout.addWidget(form_group)

        layout.addSpacing(16)

        register_link = QPushButton("还没有账号？点击注册")
        register_link.setFlat(True)
        register_link.setCursor(Qt.CursorShape.PointingHandCursor)
        register_link.setStyleSheet(
            "QPushButton { border: none; color: #3498DB; font-size: 13px; background: transparent; text-align: center; }"
            "QPushButton:hover { color: #2980B9; text-decoration: underline; }"
        )
        register_link.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout.addWidget(register_link)

        layout.addStretch()

        return page

    def _build_register_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addSpacing(20)

        title = QLabel("注册新账号")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #2C3E50; background: transparent;")
        layout.addWidget(title)

        layout.addSpacing(30)

        form_group = QGroupBox()
        form_group.setStyleSheet(
            "QGroupBox { background-color: #FFFFFF; border: 1px solid #E0E0E0; "
            "border-radius: 8px; padding: 24px 20px; margin-top: 0; }"
        )
        form_layout = QVBoxLayout(form_group)
        form_layout.setSpacing(12)

        self.reg_username = QLineEdit()
        self.reg_username.setPlaceholderText("用户名")
        self.reg_username.setFixedHeight(40)
        self.reg_username.setStyleSheet(
            "QLineEdit { border: 1px solid #DDD; border-radius: 4px; "
            "padding: 8px 12px; font-size: 14px; }"
            "QLineEdit:focus { border: 1px solid #3498DB; }"
        )
        form_layout.addWidget(self.reg_username)

        self.reg_password = QLineEdit()
        self.reg_password.setPlaceholderText("密码（至少6位）")
        self.reg_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_password.setFixedHeight(40)
        self.reg_password.setStyleSheet(
            "QLineEdit { border: 1px solid #DDD; border-radius: 4px; "
            "padding: 8px 12px; font-size: 14px; }"
            "QLineEdit:focus { border: 1px solid #3498DB; }"
        )
        form_layout.addWidget(self.reg_password)

        self.reg_confirm = QLineEdit()
        self.reg_confirm.setPlaceholderText("确认密码")
        self.reg_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_confirm.setFixedHeight(40)
        self.reg_confirm.setStyleSheet(
            "QLineEdit { border: 1px solid #DDD; border-radius: 4px; "
            "padding: 8px 12px; font-size: 14px; }"
            "QLineEdit:focus { border: 1px solid #3498DB; }"
        )
        self.reg_confirm.returnPressed.connect(self._on_register)
        form_layout.addWidget(self.reg_confirm)

        self.reg_role = QComboBox()
        self.reg_role.setFixedHeight(40)
        self.reg_role.addItem("一线客服", "frontline_staff")
        self.reg_role.addItem("部门主管", "department_manager")
        self.reg_role.addItem("总经理", "general_manager")
        self.reg_role.setStyleSheet(
            "QComboBox { border: 1px solid #DDD; border-radius: 4px; "
            "padding: 8px 12px; font-size: 14px; }"
            "QComboBox::drop-down { border: none; width: 30px; }"
        )
        form_layout.addWidget(self.reg_role)

        self.register_btn = QPushButton("注 册")
        self.register_btn.setFixedHeight(44)
        self.register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: #FFFFFF; border: none; "
            "border-radius: 4px; font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #43A047; }"
            "QPushButton:disabled { background-color: #BDC3C7; }"
        )
        self.register_btn.clicked.connect(self._on_register)
        form_layout.addWidget(self.register_btn)

        self.reg_error = QLabel("")
        self.reg_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_error.setStyleSheet("color: #FF4444; font-size: 13px; background: transparent;")
        self.reg_error.setFixedHeight(20)
        form_layout.addWidget(self.reg_error)

        layout.addWidget(form_group)

        layout.addSpacing(16)

        login_link = QPushButton("已有账号？点击登录")
        login_link.setFlat(True)
        login_link.setCursor(Qt.CursorShape.PointingHandCursor)
        login_link.setStyleSheet(
            "QPushButton { border: none; color: #3498DB; font-size: 13px; background: transparent; text-align: center; }"
            "QPushButton:hover { color: #2980B9; text-decoration: underline; }"
        )
        login_link.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        layout.addWidget(login_link)

        layout.addStretch()

        return page

    def _on_login(self):
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()

        if not username or not password:
            self.login_error.setText("请输入用户名和密码")
            return

        self.login_error.setText("")
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")

        self._login_thread = LoginThread(self.api_client, username, password)
        self._login_thread.finished.connect(self._on_login_result)
        self._login_thread.start()

    def _on_login_result(self, result):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("登 录")

        if result is None:
            self.login_error.setText("网络错误，请检查后端服务")
            return

        if result.get("code") != 0:
            self.login_error.setText(result.get("message", "登录失败"))
            return

        data = result.get("data", {})
        self.api_client.token = data.get("token")
        self.api_client.user_info = data
        self.login_success.emit(data)

    def _on_register(self):
        username = self.reg_username.text().strip()
        password = self.reg_password.text().strip()
        confirm = self.reg_confirm.text().strip()
        role = self.reg_role.currentData()

        if not username:
            self.reg_error.setText("请输入用户名")
            return
        if len(password) < 6:
            self.reg_error.setText("密码长度至少6位")
            return
        if password != confirm:
            self.reg_error.setText("两次密码不一致")
            return

        self.reg_error.setText("")
        self.register_btn.setEnabled(False)
        self.register_btn.setText("注册中...")

        self._register_thread = RegisterThread(self.api_client, username, password, role)
        self._register_thread.finished.connect(self._on_register_result)
        self._register_thread.start()

    def _on_register_result(self, result):
        self.register_btn.setEnabled(True)
        self.register_btn.setText("注 册")

        if result is None:
            self.reg_error.setText("网络错误，请检查后端服务")
            return

        if result.get("code") != 0:
            self.reg_error.setText(result.get("message", "注册失败"))
            return

        self.reg_username.clear()
        self.reg_password.clear()
        self.reg_confirm.clear()
        self.reg_error.setText("")

        self.login_error.setStyleSheet("color: #4CAF50; font-size: 13px; background: transparent;")
        self.login_error.setText("注册成功，请登录")

        self.stack.setCurrentIndex(0)
