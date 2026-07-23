import os
import tempfile
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QGridLayout, QSizePolicy, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from desktop.api_client import ApiClient

# 尝试导入 matplotlib
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    # 设置中文字体
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# 问题分类标签映射
CATEGORY_LABELS = {
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

# 处理动作类型标签映射（v1.2: 原出单类型分布）
ACTION_TYPE_LABELS = {
    "Auto_Reply": "自动回复",
    "Routed": "已路由",
    "Manual_Resolved": "人工解决",
    "Escalated": "已升级",
}


class LoadDashboardThread(QThread):
    """加载质量看板数据线程"""
    finished = pyqtSignal(object)

    def __init__(self, api_client, start_date=None, end_date=None, model_number=None):
        super().__init__()
        self.api_client = api_client
        self.start_date = start_date
        self.end_date = end_date
        self.model_number = model_number

    def run(self):
        result = self.api_client.get_quality_dashboard(
            start_date=self.start_date,
            end_date=self.end_date,
            model_number=self.model_number,
        )
        self.finished.emit(result)


class ExportReportThread(QThread):
    """导出质量报表线程"""
    finished = pyqtSignal(object)

    def __init__(self, api_client, format="xlsx", model_number=None, start_date=None, end_date=None):
        super().__init__()
        self.api_client = api_client
        self.format = format
        self.model_number = model_number
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        result = self.api_client.export_quality_report(
            format=self.format,
            model_number=self.model_number,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        self.finished.emit(result)


class StatCard(QWidget):
    """统计卡片组件"""

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


class ChartCanvas(FigureCanvas):
    """matplotlib 图表画布"""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor("#FFFFFF")
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class QualityAnalysisView(QWidget):
    """质量分析看板视图"""

    def __init__(self, api_client: ApiClient, role=None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._role = role
        self._load_thread = None
        self._export_thread = None
        self._start_date = None
        self._end_date = None
        self._model_number = None
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 顶部标题栏
        header_layout = QHBoxLayout()
        title = QLabel("质量分析看板")
        title.setObjectName("page_title")
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # 筛选栏：日期范围 + 型号
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        filter_layout.addWidget(QLabel("日期范围："))
        self.date_range_combo = QComboBox()
        self.date_range_combo.addItem("近7天", 7)
        self.date_range_combo.addItem("近30天", 30)
        self.date_range_combo.addItem("近90天", 90)
        self.date_range_combo.addItem("自定义", 0)
        self.date_range_combo.setFixedWidth(120)
        self.date_range_combo.currentIndexChanged.connect(self._on_date_range_changed)
        filter_layout.addWidget(self.date_range_combo)

        filter_layout.addWidget(QLabel("型号："))
        self.model_combo = QComboBox()
        self.model_combo.addItem("全部", "")
        self.model_combo.setFixedWidth(160)
        self.model_combo.setEditable(True)
        filter_layout.addWidget(self.model_combo)

        self.query_btn = QPushButton("查询")
        self.query_btn.clicked.connect(self._on_query)
        filter_layout.addWidget(self.query_btn)

        self.reset_filter_btn = QPushButton("重置")
        self.reset_filter_btn.clicked.connect(self._on_reset_filter)
        filter_layout.addWidget(self.reset_filter_btn)

        filter_layout.addStretch()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._load_data)
        filter_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(filter_layout)

        # 统计卡片区域
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.card_total_tickets = StatCard("📋", "投诉总量", "0", "#1E2329")
        self.card_total_archived = StatCard("📦", "归档总量", "0", "#1E2329")
        self.card_high_urgency = StatCard("🔥", "高紧急率", "0%", "#A8423A")
        self.card_archive_rate = StatCard("✅", "归档完整率", "0%", "#3A7D5F")

        cards_layout.addWidget(self.card_total_tickets)
        cards_layout.addWidget(self.card_total_archived)
        cards_layout.addWidget(self.card_high_urgency)
        cards_layout.addWidget(self.card_archive_rate)
        main_layout.addLayout(cards_layout)

        # 图表区域
        if HAS_MATPLOTLIB:
            self._setup_chart_layout(main_layout)
        else:
            self._setup_table_layout(main_layout)

        # 底部导出按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.export_xlsx_btn = QPushButton("导出Excel报表")
        self.export_xlsx_btn.setProperty("success", True)
        self.export_xlsx_btn.setStyleSheet(
            "QPushButton { background-color: #3A7D5F; color: #FFFFFF; border: none; "
            "border-radius: 6px; padding: 8px 20px; font-weight: 500; font-size: 13px; }"
            "QPushButton:hover { background-color: #336D52; }"
        )
        self.export_xlsx_btn.clicked.connect(lambda: self._on_export("xlsx"))
        bottom_layout.addWidget(self.export_xlsx_btn)

        self.export_csv_btn = QPushButton("导出CSV报表")
        self.export_csv_btn.setProperty("secondary", True)
        self.export_csv_btn.setStyleSheet(
            "QPushButton { background-color: #FFFFFF; color: #1E2329; border: 1px solid #EAEDF2; "
            "border-radius: 6px; padding: 8px 20px; font-weight: 500; font-size: 13px; }"
            "QPushButton:hover { border-color: #C9A86A; }"
        )
        self.export_csv_btn.clicked.connect(lambda: self._on_export("csv"))
        bottom_layout.addWidget(self.export_csv_btn)

        main_layout.addLayout(bottom_layout)

    def _setup_chart_layout(self, main_layout):
        """使用 matplotlib 创建图表布局"""
        charts_top = QHBoxLayout()
        charts_top.setSpacing(16)

        # 投诉趋势柱状图
        trend_group = QGroupBox("投诉趋势（近30日）")
        trend_layout = QVBoxLayout(trend_group)
        self.trend_canvas = ChartCanvas(self, width=5, height=3)
        trend_layout.addWidget(self.trend_canvas)
        charts_top.addWidget(trend_group)

        # 处理动作分布饼图（v1.2: 原出单类型分布）
        action_type_group = QGroupBox("处理动作分布")
        action_type_layout = QVBoxLayout(action_type_group)
        self.order_type_canvas = ChartCanvas(self, width=5, height=3)
        action_type_layout.addWidget(self.order_type_canvas)
        charts_top.addWidget(action_type_group)

        main_layout.addLayout(charts_top, 3)

        charts_bottom = QHBoxLayout()
        charts_bottom.setSpacing(16)

        # 产品型号投诉排名横向柱状图
        model_group = QGroupBox("产品型号投诉排名")
        model_layout = QVBoxLayout(model_group)
        self.model_canvas = ChartCanvas(self, width=5, height=3)
        model_layout.addWidget(self.model_canvas)
        charts_bottom.addWidget(model_group)

        # 问题分类分布饼图
        category_group = QGroupBox("问题分类分布")
        category_layout = QVBoxLayout(category_group)
        self.category_canvas = ChartCanvas(self, width=5, height=3)
        category_layout.addWidget(self.category_canvas)
        charts_bottom.addWidget(category_group)

        main_layout.addLayout(charts_bottom, 3)

    def _setup_table_layout(self, main_layout):
        """使用 QTableWidget 替代图表（matplotlib 不可用时）"""
        tables_top = QHBoxLayout()
        tables_top.setSpacing(16)

        # 投诉趋势表
        trend_group = QGroupBox("投诉趋势（近30日）")
        trend_layout = QVBoxLayout(trend_group)
        self.trend_table = QTableWidget()
        self.trend_table.setColumnCount(2)
        self.trend_table.setHorizontalHeaderLabels(["日期", "投诉数量"])
        self.trend_table.horizontalHeader().setStretchLastSection(True)
        self.trend_table.verticalHeader().setVisible(False)
        self.trend_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        trend_layout.addWidget(self.trend_table)
        tables_top.addWidget(trend_group)

        # 处理动作分布表（v1.2: 原出单类型分布）
        action_type_group = QGroupBox("处理动作分布")
        action_type_layout = QVBoxLayout(action_type_group)
        self.order_type_table = QTableWidget()
        self.order_type_table.setColumnCount(2)
        self.order_type_table.setHorizontalHeaderLabels(["处理动作", "数量"])
        self.order_type_table.horizontalHeader().setStretchLastSection(True)
        self.order_type_table.verticalHeader().setVisible(False)
        self.order_type_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        action_type_layout.addWidget(self.order_type_table)
        tables_top.addWidget(action_type_group)

        main_layout.addLayout(tables_top, 3)

        tables_bottom = QHBoxLayout()
        tables_bottom.setSpacing(16)

        # 产品型号投诉排名表
        model_group = QGroupBox("产品型号投诉排名")
        model_layout = QVBoxLayout(model_group)
        self.model_table = QTableWidget()
        self.model_table.setColumnCount(2)
        self.model_table.setHorizontalHeaderLabels(["产品型号", "投诉数量"])
        self.model_table.horizontalHeader().setStretchLastSection(True)
        self.model_table.verticalHeader().setVisible(False)
        self.model_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        model_layout.addWidget(self.model_table)
        tables_bottom.addWidget(model_group)

        # 问题分类分布表
        category_group = QGroupBox("问题分类分布")
        category_layout = QVBoxLayout(category_group)
        self.category_table = QTableWidget()
        self.category_table.setColumnCount(2)
        self.category_table.setHorizontalHeaderLabels(["问题分类", "数量"])
        self.category_table.horizontalHeader().setStretchLastSection(True)
        self.category_table.verticalHeader().setVisible(False)
        self.category_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        category_layout.addWidget(self.category_table)
        tables_bottom.addWidget(category_group)

        main_layout.addLayout(tables_bottom, 3)

    def _get_date_range(self):
        """获取日期范围"""
        days = self.date_range_combo.currentData()
        if days and days > 0:
            end = datetime.now()
            start = end - timedelta(days=days)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        return self._start_date, self._end_date

    def _on_date_range_changed(self, index):
        """日期范围切换"""
        days = self.date_range_combo.currentData()
        if days == 0:
            # 自定义日期范围 - 暂不实现日期选择器，使用默认范围
            pass

    def _on_query(self):
        """查询按钮点击"""
        self._model_number = self.model_combo.currentData() or None
        self._start_date, self._end_date = self._get_date_range()
        self._load_data()

    def _on_reset_filter(self):
        """重置筛选条件"""
        self.date_range_combo.setCurrentIndex(1)  # 近30天
        self.model_combo.setCurrentIndex(0)
        self._model_number = None
        self._start_date = None
        self._end_date = None
        self._load_data()

    def _load_data(self):
        """加载质量看板数据"""
        self._set_controls_enabled(False)

        start_date, end_date = self._get_date_range()
        model_number = self.model_combo.currentData() or None

        self._load_thread = LoadDashboardThread(
            self.api_client,
            start_date=start_date,
            end_date=end_date,
            model_number=model_number,
        )
        self._load_thread.finished.connect(self._on_data_loaded)
        self._load_thread.start()

    def _set_controls_enabled(self, enabled):
        """设置控件启用/禁用状态"""
        self.query_btn.setEnabled(enabled)
        self.reset_filter_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        self.export_xlsx_btn.setEnabled(enabled)
        self.export_csv_btn.setEnabled(enabled)

    def _on_data_loaded(self, result):
        """数据加载完成"""
        self._set_controls_enabled(True)

        if result is None:
            self.card_total_tickets.set_value("N/A")
            self.card_total_archived.set_value("N/A")
            self.card_high_urgency.set_value("N/A")
            self.card_archive_rate.set_value("N/A")
            return

        data = result.get("data", {}) if isinstance(result, dict) else {}
        if not data:
            return

        # 更新统计卡片
        overview = data.get("overview", {})
        total_tickets = overview.get("total_tickets", 0)
        total_archived = overview.get("total_archived", 0)
        high_urgency_rate = overview.get("high_urgency_rate", 0)
        archive_complete_rate = overview.get("archive_complete_rate", 0)

        self.card_total_tickets.set_value(str(total_tickets))
        self.card_total_archived.set_value(str(total_archived))
        self.card_high_urgency.set_value(f"{high_urgency_rate}%")
        self.card_archive_rate.set_value(f"{archive_complete_rate}%")

        # 更新图表
        trend = data.get("trend", {})
        top_models = data.get("top_models", [])
        category_distribution = data.get("category_distribution", {})
        action_type_distribution = data.get("action_type_distribution", {})

        if HAS_MATPLOTLIB:
            self._update_trend_chart(trend)
            self._update_order_type_chart(action_type_distribution)
            self._update_model_chart(top_models)
            self._update_category_chart(category_distribution)
        else:
            self._update_trend_table(trend)
            self._update_order_type_table(action_type_distribution)
            self._update_model_table(top_models)
            self._update_category_table(category_distribution)

    def _update_trend_chart(self, trend):
        """更新投诉趋势柱状图"""
        self.trend_canvas.fig.clear()
        ax = self.trend_canvas.fig.add_subplot(111)

        daily = trend.get("daily", {})
        if not daily:
            ax.text(0.5, 0.5, "暂无趋势数据", ha="center", va="center", fontsize=12, color="#BDC3C7")
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            dates = list(daily.keys())
            values = list(daily.values())
            # 简化日期显示
            short_dates = []
            for d in dates:
                parts = d.split("-")
                short_dates.append(f"{parts[1]}-{parts[2]}" if len(parts) == 3 else d)

            ax.bar(short_dates, values, color="#3498DB", alpha=0.8)
            ax.set_xlabel("日期", fontsize=10)
            ax.set_ylabel("投诉数量", fontsize=10)
            ax.tick_params(axis="x", rotation=45, labelsize=8)

        self.trend_canvas.fig.tight_layout()
        self.trend_canvas.draw()

    def _update_order_type_chart(self, distribution):
        """更新处理动作分布饼图（v1.2: 原出单类型分布）"""
        self.order_type_canvas.fig.clear()
        ax = self.order_type_canvas.fig.add_subplot(111)

        if not distribution:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=12, color="#BDC3C7")
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            labels = [ACTION_TYPE_LABELS.get(k, k) for k in distribution.keys()]
            values = list(distribution.values())
            colors = ["#3498DB", "#2ECC71", "#E74C3C", "#F39C12", "#9B59B6"]
            ax.pie(values, labels=labels, autopct="%1.1f%%", colors=colors[:len(values)],
                   startangle=90, textprops={"fontsize": 9})

        self.order_type_canvas.fig.tight_layout()
        self.order_type_canvas.draw()

    def _update_model_chart(self, top_models):
        """更新产品型号投诉排名横向柱状图"""
        self.model_canvas.fig.clear()
        ax = self.model_canvas.fig.add_subplot(111)

        if not top_models:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=12, color="#BDC3C7")
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            # 取前10名
            models = top_models[:10]
            names = [m.get("model_number", "-") for m in reversed(models)]
            counts = [m.get("ticket_count", 0) for m in reversed(models)]
            ax.barh(names, counts, color="#E74C3C", alpha=0.8)
            ax.set_xlabel("投诉数量", fontsize=10)
            ax.tick_params(axis="y", labelsize=9)

        self.model_canvas.fig.tight_layout()
        self.model_canvas.draw()

    def _update_category_chart(self, distribution):
        """更新问题分类分布饼图"""
        self.category_canvas.fig.clear()
        ax = self.category_canvas.fig.add_subplot(111)

        if not distribution:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=12, color="#BDC3C7")
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            labels = [CATEGORY_LABELS.get(k, k) for k in distribution.keys()]
            values = list(distribution.values())
            colors = ["#3498DB", "#2ECC71", "#E74C3C", "#F39C12", "#9B59B6",
                      "#1ABC9C", "#E67E22", "#34495E", "#95A5A6"]
            ax.pie(values, labels=labels, autopct="%1.1f%%", colors=colors[:len(values)],
                   startangle=90, textprops={"fontsize": 9})

        self.category_canvas.fig.tight_layout()
        self.category_canvas.draw()

    def _update_trend_table(self, trend):
        """更新投诉趋势表格（matplotlib 不可用时）"""
        daily = trend.get("daily", {})
        self.trend_table.setRowCount(len(daily))
        for row, (date_str, count) in enumerate(daily.items()):
            self.trend_table.setItem(row, 0, QTableWidgetItem(date_str))
            self.trend_table.setItem(row, 1, QTableWidgetItem(str(count)))

    def _update_order_type_table(self, distribution):
        """更新处理动作分布表格（v1.2: 原出单类型分布）"""
        self.order_type_table.setRowCount(len(distribution))
        for row, (key, count) in enumerate(distribution.items()):
            label = ACTION_TYPE_LABELS.get(key, key)
            self.order_type_table.setItem(row, 0, QTableWidgetItem(label))
            self.order_type_table.setItem(row, 1, QTableWidgetItem(str(count)))

    def _update_model_table(self, top_models):
        """更新产品型号投诉排名表格"""
        self.model_table.setRowCount(len(top_models))
        for row, model in enumerate(top_models):
            self.model_table.setItem(row, 0, QTableWidgetItem(model.get("model_number", "-")))
            self.model_table.setItem(row, 1, QTableWidgetItem(str(model.get("ticket_count", 0))))

    def _update_category_table(self, distribution):
        """更新问题分类分布表格"""
        self.category_table.setRowCount(len(distribution))
        for row, (key, count) in enumerate(distribution.items()):
            label = CATEGORY_LABELS.get(key, key)
            self.category_table.setItem(row, 0, QTableWidgetItem(label))
            self.category_table.setItem(row, 1, QTableWidgetItem(str(count)))

    def _on_export(self, format):
        """导出质量报表"""
        self._set_controls_enabled(False)

        start_date, end_date = self._get_date_range()
        model_number = self.model_combo.currentData() or None

        self._export_thread = ExportReportThread(
            self.api_client,
            format=format,
            model_number=model_number,
            start_date=start_date,
            end_date=end_date,
        )
        self._export_thread.finished.connect(lambda result: self._on_export_done(result, format))
        self._export_thread.start()

    def _on_export_done(self, result, format):
        """导出完成回调"""
        self._set_controls_enabled(True)

        if result is None:
            QMessageBox.warning(self, "导出失败", "无法导出报表，请检查网络连接或后端服务")
            return

        if not isinstance(result, bytes):
            QMessageBox.warning(self, "导出失败", "导出返回数据格式异常")
            return

        # 选择保存路径
        ext = "xlsx" if format == "xlsx" else "csv"
        filter_str = f"Excel文件 (*.{ext})" if format == "xlsx" else f"CSV文件 (*.{ext})"
        default_name = f"quality_report.{ext}"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存报表", default_name, filter_str
        )

        if filepath:
            try:
                with open(filepath, "wb") as f:
                    f.write(result)
                QMessageBox.information(self, "导出成功", f"报表已保存到：\n{filepath}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"保存文件失败：{str(e)}")
