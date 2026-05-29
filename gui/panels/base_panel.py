#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
封装厂面板基类

提供公共 UI 元素：数据类型按钮组、文件夹选择、开始按钮、状态日志区。
子类只需定义 data_types 列表和 _run_cleaner 方法。
"""

import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTextEdit, QGroupBox,
                             QFileDialog, QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


class CleanerWorker(QThread):
    """清洗工作线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str, bool)
    error = pyqtSignal(str)

    def __init__(self, task_fn, task_label: str):
        super().__init__()
        self.task_fn = task_fn
        self.task_label = task_label

    def run(self):
        try:
            self.progress.emit(f"开始 {self.task_label}...")
            result = self.task_fn()
            if result:
                self.finished.emit(f"{self.task_label} 完成", True)
            else:
                self.finished.emit(f"{self.task_label} 失败", False)
        except Exception as e:
            self.error.emit(str(e))


class BasePanel(QWidget):
    """
    封装厂面板基类。

    子类需设置：
        - factory_name: 工厂名称
        - data_types: 数据类型列表，如 ["DC", "DVDS", "RG", "PAT"]
        - default_input: 默认输入路径
        - default_output: 默认输出路径
    并实现：
        - _get_cleaner_fn(data_type: str) -> callable
    """

    factory_name: str = ""
    data_types: list = []
    default_input: str = ""
    default_output: str = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: CleanerWorker = None
        self._selected_type: str = ""
        self._type_buttons: dict = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 数据类型按钮组
        layout.addWidget(self._build_type_group())
        # 文件夹选择
        layout.addWidget(self._build_folder_group())
        # 开始按钮
        layout.addLayout(self._build_action_buttons())
        # 状态显示
        layout.addWidget(self._build_status_group())

    def _build_type_group(self) -> QGroupBox:
        group = QGroupBox(f"{self.factory_name} - 数据类型选择")
        group.setStyleSheet(self._group_style())
        hbox = QHBoxLayout(group)

        for i, dt in enumerate(self.data_types):
            btn = QPushButton(dt)
            btn.setCheckable(True)
            btn.setMinimumHeight(45)
            btn.setMinimumWidth(100)
            btn.clicked.connect(lambda checked, t=dt: self._on_type_selected(t))
            self._type_buttons[dt] = btn
            hbox.addWidget(btn)
            if i == 0:
                btn.setChecked(True)
                self._selected_type = dt

        hbox.addStretch()
        return group

    def _build_folder_group(self) -> QGroupBox:
        group = QGroupBox("文件夹选择")
        group.setStyleSheet(self._group_style())
        vbox = QVBoxLayout(group)

        # 输入
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("数据文件夹:"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择数据文件夹...")
        h1.addWidget(self.input_edit)
        btn_in = QPushButton("选择...")
        btn_in.clicked.connect(self._browse_input)
        h1.addWidget(btn_in)
        vbox.addLayout(h1)

        # 输出
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("输出文件夹:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择输出文件夹...")
        h2.addWidget(self.output_edit)
        btn_out = QPushButton("选择...")
        btn_out.clicked.connect(self._browse_output)
        h2.addWidget(btn_out)
        vbox.addLayout(h2)

        return group

    def _build_action_buttons(self) -> QHBoxLayout:
        hbox = QHBoxLayout()
        hbox.addStretch()
        self.start_btn = QPushButton("🚀 开始清洗")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setMinimumWidth(250)
        self.start_btn.clicked.connect(self._start)
        self.start_btn.setStyleSheet(
            "QPushButton{background:#2196F3;font-size:24px;}"
            "QPushButton:hover{background:#1976D2;}"
        )
        hbox.addWidget(self.start_btn)
        hbox.addStretch()
        return hbox

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("处理状态")
        group.setStyleSheet(self._group_style())
        vbox = QVBoxLayout(group)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(200)
        self.status_text.setPlaceholderText("等待操作...")
        vbox.addWidget(self.status_text)
        return group

    def _group_style(self) -> str:
        return """
            QGroupBox{font-weight:bold;border:2px solid #ccc;border-radius:6px;
            margin-top:8px;padding:12px;font-size:20px;}
            QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px;}
        """

    def _on_type_selected(self, data_type: str):
        self._selected_type = data_type
        self._log(f"选择: {data_type}")

    def _browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "选择数据文件夹", 
                                                   self.input_edit.text() or os.path.expanduser("~"))
        if folder:
            self.input_edit.setText(folder)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹",
                                                   self.output_edit.text() or os.path.expanduser("~"))
        if folder:
            self.output_edit.setText(folder)

    def _start(self):
        if not self._selected_type:
            QMessageBox.warning(self, "提示", "请先选择数据类型")
            return
        if not self.input_edit.text().strip():
            QMessageBox.warning(self, "提示", "请选择数据文件夹")
            return
        if not self.output_edit.text().strip():
            QMessageBox.warning(self, "提示", "请选择输出文件夹")
            return

        self.status_text.clear()
        self.start_btn.setEnabled(False)
        self.start_btn.setText("清洗中...")

        worker_fn = self._get_cleaner_fn(self._selected_type)
        self.worker = CleanerWorker(worker_fn, f"{self.factory_name} {self._selected_type}")
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _get_cleaner_fn(self, data_type: str):
        """子类重写：返回一个可调用对象（无参数），执行清洗"""
        raise NotImplementedError

    def _on_progress(self, msg: str):
        self._log(msg)

    def _on_finished(self, msg: str, success: bool):
        self._log(f"🎉 {msg}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("🚀 开始清洗")
        if success:
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def _on_error(self, err: str):
        self._log(f"❌ 错误: {err}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("🚀 开始清洗")
        QMessageBox.critical(self, "错误", err)

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{ts}] {msg}")
        sb = self.status_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_default_paths(self, input_path: str, output_path: str):
        self.input_edit.setText(input_path)
        self.output_edit.setText(output_path)
