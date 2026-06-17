from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import pyqtSignal


class ExportDialog(QDialog):
    """数据导出对话框"""

    export_requested = pyqtSignal(str, str)  # format, scope

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出数据")
        self.setMinimumWidth(320)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 导出格式
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("导出格式："))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Excel (.xlsx)", "CSV (.csv)"])
        format_layout.addWidget(self.format_combo)
        layout.addLayout(format_layout)

        # 导出范围
        scope_label = QLabel("导出范围：")
        layout.addWidget(scope_label)

        self.scope_group = QButtonGroup(self)
        self.radio_current = QRadioButton("当前筛选结果")
        self.radio_current.setChecked(True)
        self.scope_group.addButton(self.radio_current)
        layout.addWidget(self.radio_current)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        export_btn = QPushButton("导出")
        export_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: #FFFFFF; border: none; "
            "border-radius: 4px; padding: 8px 24px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(
            "QPushButton { background-color: #BDC3C7; color: #2C3E50; border: none; "
            "border-radius: 4px; padding: 8px 24px; font-size: 13px; }"
            "QPushButton:hover { background-color: #AAB7B8; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _on_export(self):
        format_str = "xlsx" if self.format_combo.currentIndex() == 0 else "csv"
        scope = "current" if self.radio_current.isChecked() else "all"
        self.export_requested.emit(format_str, scope)
        self.accept()

    def get_format(self) -> str:
        """获取选择的导出格式"""
        return "xlsx" if self.format_combo.currentIndex() == 0 else "csv"

    def get_scope(self) -> str:
        """获取选择的导出范围"""
        return "current" if self.radio_current.isChecked() else "all"
