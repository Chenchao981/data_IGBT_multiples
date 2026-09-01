#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FT数据清洗工具 — 多封装厂主界面

左侧：封装厂列表（QListWidget）
右侧：封装厂面板（QStackedWidget 动态切换）
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QVBoxLayout, QListWidget, QListWidgetItem,
                             QStackedWidget, QLabel, QFrame, QSplitter,
                             QStyledItemDelegate, QStyle)
from PyQt5.QtCore import Qt, QSize, QRectF
from PyQt5.QtGui import QFont, QColor, QPainter, QPen

from gui.panels.riyuexin_panel import RiyuexinPanel
from gui.panels.jiequn_panel import JiequnPanel
from gui.panels.dianji_panel import DianjiPanel
from gui.panels.jijia_panel import JijiaPanel


FACTORIES = [
    {"name": "日月新 (Riyuexin)", "panel": RiyuexinPanel, "color": "#BDE7F8", "accent": "#38BDF8"},
    {"name": "杰群 (Jiequn)", "panel": JiequnPanel, "color": "#FFD1DC", "accent": "#FB7185"},
    {"name": "电基 (Dianji)", "panel": DianjiPanel, "color": "#D8F3C9", "accent": "#84CC16"},
    {"name": "集佳 (Jijia)", "panel": JijiaPanel, "color": "#E3D5FF", "accent": "#8B5CF6"},
]


class FactoryItemDelegate(QStyledItemDelegate):
    """Paint each factory as a separate pastel button."""

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        base_color = QColor(index.data(Qt.UserRole + 1) or "#ffffff")
        accent_color = QColor(index.data(Qt.UserRole + 2) or "#ffb4a2")
        rect = option.rect.adjusted(0, 2, 0, -2)
        button_rect = QRectF(rect).adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)

        fill = QColor(base_color)
        if hover:
            fill = fill.lighter(106)
        painter.setBrush(fill)
        painter.setPen(QPen(accent_color, 3 if selected else 1))
        painter.drawRoundedRect(button_rect, 10, 10)

        marker_rect = QRectF(button_rect.left() + 13, button_rect.top() + 14, 14, 14)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent_color)
        painter.drawRoundedRect(marker_rect, 3, 3)

        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        text_rect = button_rect.adjusted(36, 0, -10, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, index.data(Qt.DisplayRole))
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(190, 58)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FT 数据清洗工具 - 多封装厂")
        self.setGeometry(100, 100, 1400, 900)
        self._panels = {}
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # 整体水平布局
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ---- 左侧边栏 ----
        sidebar = QFrame()
        sidebar.setFixedWidth(238)
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet("""
            QFrame#sidebar{
                background:#fff7f2;
                border-right:1px solid #f1d9d0;
            }
        """)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 16, 14, 16)
        side_layout.setSpacing(12)

        # 标题
        title = QLabel("封装厂选择")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color:#334155;
            font-size:23px;
            font-weight:bold;
            padding:12px 8px 14px 8px;
            background:#ffffff;
            border:1px solid #f0d9d2;
            border-radius:10px;
        """)
        side_layout.addWidget(title)

        # 工厂列表
        self.factory_list = QListWidget()
        self.factory_list.setItemDelegate(FactoryItemDelegate(self.factory_list))
        self.factory_list.setSpacing(8)
        self.factory_list.setStyleSheet("""
            QListWidget{
                background:transparent;
                color:#334155;
                border:none;
                font-size:18px;
                font-weight:600;
                outline:0;
            }
            QListWidget::item{
                background:transparent;
                border:none;
            }
        """)
        for f in FACTORIES:
            item = QListWidgetItem(f["name"])
            item.setSizeHint(QSize(190, 58))
            item.setData(Qt.UserRole, f["panel"])
            item.setData(Qt.UserRole + 1, f["color"])
            item.setData(Qt.UserRole + 2, f["accent"])
            self.factory_list.addItem(item)

        self.factory_list.currentRowChanged.connect(self._on_factory_changed)
        side_layout.addWidget(self.factory_list)
        side_layout.addStretch()

        # ---- 右侧面板区 ----
        self.stack = QStackedWidget()
        for f in FACTORIES:
            panel = f["panel"]()
            self.stack.addWidget(panel)
            self._panels[f["name"]] = panel

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(self.stack)
        splitter.setSizes([238, 1162])

        main_layout.addWidget(splitter)

        # 默认选第一个
        self.factory_list.setCurrentRow(0)

    def _on_factory_changed(self, index: int):
        item = self.factory_list.item(index)
        if item:
            name = item.text()
            if name in self._panels:
                self.stack.setCurrentWidget(self._panels[name])

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FT数据清洗工具")
    app.setApplicationVersion("2.19.0")

    app.setStyleSheet("""
        QMainWindow{background:#f7fbfb;}
        QWidget{font-family:"Microsoft YaHei","Segoe UI",Arial;}
        QPushButton{
            background:#5aa9e6;
            color:#ffffff;
            border:none;
            padding:9px 18px;
            border-radius:8px;
            font-size:18px;
            font-weight:700;
        }
        QPushButton:hover{background:#3f95d8;}
        QPushButton:pressed{background:#2f80c4;}
        QPushButton:disabled{background:#d8e2e8;color:#7b8794;}
        QPushButton:checked{
            background:#95d5b2;
            color:#123524;
            border:2px solid #52b788;
        }
        QLineEdit,QTextEdit{
            padding:8px 10px;
            border:1px solid #b8c4cc;
            border-radius:7px;
            font-size:16px;
            background:#ffffff;
            color:#1f2937;
            selection-background-color:#ffd6a5;
        }
        QLineEdit:focus,QTextEdit:focus{border:2px solid #7bdff2;}
        QLabel{font-size:17px;color:#334155;}
        QGroupBox{font-weight:bold;font-size:18px;margin-top:8px;color:#111827;}
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
