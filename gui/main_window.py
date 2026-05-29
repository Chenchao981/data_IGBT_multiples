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
                             QStackedWidget, QLabel, QFrame, QSplitter)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.panels.riyuexin_panel import RiyuexinPanel
from gui.panels.jiequn_panel import JiequnPanel


FACTORIES = [
    {"name": "日月新 (ASE)", "panel": RiyuexinPanel},
    {"name": "杰群 (Jiequn)", "panel": JiequnPanel},
]


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
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("QFrame{background:#2c3e50;}")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("封装厂选择")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:white;font-size:22px;font-weight:bold;padding:15px;")
        side_layout.addWidget(title)

        # 工厂列表
        self.factory_list = QListWidget()
        self.factory_list.setStyleSheet("""
            QListWidget{background:#34495e;color:white;border:none;font-size:18px;}
            QListWidget::item{padding:14px 16px;border-bottom:1px solid #2c3e50;}
            QListWidget::item:selected{background:#3498db;}
            QListWidget::item:hover{background:#3d566e;}
        """)
        for f in FACTORIES:
            item = QListWidgetItem(f["name"])
            item.setData(Qt.UserRole, f["panel"])
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
        splitter.setSizes([220, 1180])

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
    app.setApplicationVersion("2.0")

    app.setStyleSheet("""
        QMainWindow{background:#ecf0f1;}
        QPushButton{background:#3498db;color:white;border:none;padding:8px 16px;
                    border-radius:4px;font-size:18px;font-weight:bold;}
        QPushButton:hover{background:#2980b9;}
        QPushButton:pressed{background:#1f6fa5;}
        QPushButton:disabled{background:#bdc3c7;color:#7f8c8d;}
        QPushButton:checked{background:#2ecc71;}
        QLineEdit,QTextEdit{padding:6px;border:1px solid #bdc3c7;border-radius:4px;font-size:16px;}
        QLabel{font-size:17px;color:#2c3e50;}
        QGroupBox{font-weight:bold;font-size:18px;margin-top:6px;}
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
