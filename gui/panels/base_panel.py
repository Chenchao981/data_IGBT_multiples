#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
封装厂面板基类

提供公共 UI 元素：数据类型按钮组、文件夹选择、开始按钮、状态日志区。
子类只需定义 data_types 列表和 _run_cleaner 方法。
"""

import os
import logging
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTextEdit, QGroupBox,
                             QFileDialog, QMessageBox, QProgressBar,
                             QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


MULTI_FILE_SEPARATOR = " | "


class CleanerWorker(QThread):
    """清洗工作线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str, bool)
    error = pyqtSignal(str)

    def __init__(self, task_fn, task_label: str):
        super().__init__()
        self.task_fn = task_fn
        self.task_label = task_label
        self.result = None

    def run(self):
        writer = _SignalTextWriter(self.progress)
        log_handler = _SignalLogHandler(self.progress)
        log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger = logging.getLogger()
        old_level = root_logger.level

        try:
            self.progress.emit(f"开始 {self.task_label}...")
            if root_logger.level in (logging.NOTSET,) or root_logger.level > logging.INFO:
                root_logger.setLevel(logging.INFO)
            root_logger.addHandler(log_handler)
            with redirect_stdout(writer), redirect_stderr(writer):
                result = self.task_fn()
                self.result = result
                writer.flush()
            if result:
                self.finished.emit(f"{self.task_label} 完成", True)
            else:
                self.finished.emit(f"{self.task_label} 失败", False)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            root_logger.removeHandler(log_handler)
            root_logger.setLevel(old_level)


class _SignalTextWriter:
    """Redirect print/stdout text from a worker thread into the GUI log."""

    def __init__(self, signal):
        self.signal = signal
        self._buffer = ""

    def write(self, text: str):
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self.signal.emit(line)
        return len(text)

    def flush(self):
        line = self._buffer.strip()
        if line:
            self.signal.emit(line)
        self._buffer = ""


class _SignalLogHandler(logging.Handler):
    """Forward logging records from cleaner modules into the GUI log."""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        try:
            self.signal.emit(self.format(record))
        except Exception:
            pass


class BasePanel(QWidget):
    """
    封装厂面板基类。

    子类需设置：
        - factory_name: 工厂名称
        - data_types: 数据文件格式/清洗入口列表，如 ["DC", "DVDS", "RG"]
        - pat_analysis_types: PAT 参数分析入口列表
        - yield_analysis_types: 封装良率分析入口列表
        - default_input: 默认输入路径
        - default_output: 默认输出路径
    并实现：
        - _get_cleaner_fn(data_type: str) -> callable
    """

    factory_name: str = ""
    data_types: list = []
    post_process_types: list = []
    pat_analysis_types: list = []
    yield_analysis_types: list = []
    scatter_supported_types: list = []
    default_input: str = ""
    default_output: str = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: CleanerWorker = None
        self._selected_type: str = ""
        self._type_buttons: dict = {}
        self._path_state: dict[str, tuple[str, str]] = {}
        self._scatter_manifest_by_type: dict[str, Path] = {}
        self._type_button_group: QButtonGroup = None
        self.init_ui()
        self._apply_operation_ui(self._selected_type)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(26, 24, 26, 24)
        self.setStyleSheet("BasePanel{background:#f7fbfb;}")

        # 数据格式/处理类型按钮组
        layout.addWidget(self._build_type_group())
        # 输入与输出选择
        layout.addWidget(self._build_folder_group())
        # 开始按钮
        layout.addLayout(self._build_action_buttons())
        # 状态显示
        layout.addWidget(self._build_status_group())

    def _build_type_group(self) -> QGroupBox:
        group = QGroupBox(f"{self.factory_name} - 处理类型选择")
        group.setStyleSheet(self._group_style())
        vbox = QVBoxLayout(group)
        self._type_button_group = QButtonGroup(group)
        self._type_button_group.setExclusive(True)

        pat_types = self.pat_analysis_types or [t for t in self.post_process_types if t == "PAT"]
        yield_types = self.yield_analysis_types or [t for t in self.post_process_types if t != "PAT"]
        rows = [
            ("FT 数据清洗:", self.data_types),
            ("PAT 参数分析:", pat_types),
            ("封装良率分析:", yield_types),
        ]
        first_row = True
        for label, types in rows:
            if types:
                vbox.addLayout(self._build_type_row(label, types, select_first=first_row))
                first_row = False

        return group

    def _build_type_row(self, label: str, types: list, select_first: bool = False) -> QHBoxLayout:
        hbox = QHBoxLayout()
        row_label = QLabel(label)
        row_label.setMinimumWidth(140)
        row_label.setStyleSheet("font-weight:600;color:#475569;")
        hbox.addWidget(row_label)

        for i, dt in enumerate(types):
            btn = QPushButton(dt)
            btn.setCheckable(True)
            btn.setMinimumHeight(45)
            btn.setMinimumWidth(100)
            btn.clicked.connect(lambda checked, t=dt: self._on_type_selected(t))
            self._type_button_group.addButton(btn)
            self._type_buttons[dt] = btn
            hbox.addWidget(btn)
            if select_first and i == 0:
                btn.setChecked(True)
                self._selected_type = dt

        hbox.addStretch()
        return hbox

    def _build_folder_group(self) -> QGroupBox:
        group = QGroupBox("输入与输出")
        self.path_group = group
        group.setStyleSheet(self._group_style())
        vbox = QVBoxLayout(group)

        # 输入
        h1 = QHBoxLayout()
        self.input_label = QLabel("原始数据文件夹:")
        self.input_label.setMinimumWidth(130)
        self.input_label.setStyleSheet("font-weight:600;color:#475569;")
        h1.addWidget(self.input_label)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择数据文件夹...")
        h1.addWidget(self.input_edit)
        self.input_browse_btn = QPushButton("选择文件夹...")
        self.input_browse_btn.clicked.connect(self._browse_input)
        h1.addWidget(self.input_browse_btn)
        vbox.addLayout(h1)

        # 输出
        h2 = QHBoxLayout()
        label_output = QLabel("输出文件夹:")
        label_output.setMinimumWidth(130)
        label_output.setStyleSheet("font-weight:600;color:#475569;")
        h2.addWidget(label_output)
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
        self.scatter_btn = QPushButton("📊 FT 散点图")
        self.scatter_btn.setMinimumHeight(50)
        self.scatter_btn.setMinimumWidth(210)
        self.scatter_btn.setEnabled(False)
        self.scatter_btn.setVisible(bool(self.scatter_supported_types))
        self.scatter_btn.setToolTip("请先完成一次支持散点图的 FT 数据清洗")
        self.scatter_btn.clicked.connect(self._open_scatter)
        self.scatter_btn.setStyleSheet(
            "QPushButton{background:#2563eb;color:#ffffff;font-size:20px;"
            "border-radius:10px;padding:10px 22px;}"
            "QPushButton:hover{background:#1d4ed8;}"
            "QPushButton:pressed{background:#1e40af;}"
            "QPushButton:disabled{background:#9fb7d9;color:#eef5ff;}"
        )
        self.start_btn = QPushButton("🚀 开始清洗")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setMinimumWidth(250)
        self.start_btn.clicked.connect(self._start)
        self.start_btn.setStyleSheet(
            "QPushButton{background:#ff8fab;color:#ffffff;font-size:24px;"
            "border-radius:10px;padding:10px 28px;}"
            "QPushButton:hover{background:#fb6f92;}"
            "QPushButton:pressed{background:#e85d75;}"
            "QPushButton:disabled{background:#e8b9c5;color:#fff5f7;}"
        )
        # 用户按从左到右的业务顺序操作：先清洗，再打开散点图。
        hbox.addWidget(self.start_btn)
        hbox.addSpacing(14)
        hbox.addWidget(self.scatter_btn)
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
        self.status_text.setStyleSheet("""
            QTextEdit{
                background:#ffffff;
                border:1px solid #c7d2da;
                border-radius:8px;
                color:#334155;
                font-size:16px;
                padding:10px;
            }
        """)
        vbox.addWidget(self.status_text)
        return group

    def _group_style(self) -> str:
        return """
            QGroupBox{
                font-weight:bold;
                color:#111827;
                background:#ffffff;
                border:2px solid #c8e7ee;
                border-radius:10px;
                margin-top:10px;
                padding:14px;
                font-size:20px;
            }
            QGroupBox::title{
                subcontrol-origin:margin;
                left:14px;
                padding:0 8px;
                background:#f7fbfb;
            }
        """

    def _on_type_selected(self, data_type: str):
        previous_type = self._selected_type
        if previous_type and previous_type != data_type:
            self._path_state[previous_type] = (
                self.input_edit.text().strip(),
                self.output_edit.text().strip(),
            )
        self._selected_type = data_type
        if data_type in self._path_state:
            input_path, output_path = self._path_state[data_type]
        else:
            input_path, output_path = self._default_paths_for_type(data_type)
        self.input_edit.setText(input_path)
        self.output_edit.setText(output_path)
        self._apply_operation_ui(data_type)
        self._log(f"选择: {data_type}")

    def _browse_input(self):
        current = self.input_edit.text().strip()
        input_mode = self._input_mode_for(self._selected_type)
        selected_files = self.selected_input_files()
        if input_mode == "files" and selected_files:
            start_path = Path(selected_files[0]).parent
        else:
            start_path = Path(current) if current else Path.home() / "Desktop"
        if start_path.is_file():
            start_path = start_path.parent

        if input_mode == "files":
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "选择一个或多个清洗结果 Excel 文件",
                str(start_path),
                "Excel 文件 (*.xlsx *.xls)",
            )
            if file_paths:
                self.input_edit.setText(MULTI_FILE_SEPARATOR.join(file_paths))
            return

        if input_mode == "file":
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择良率 Excel 文件",
                str(start_path),
                "Excel 文件 (*.xlsx *.xls)",
            )
            if file_path:
                self.input_edit.setText(file_path)
            return

        folder = QFileDialog.getExistingDirectory(self, "选择输入文件夹", str(start_path))
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
        input_text = self.input_edit.text().strip()
        output_text = self.output_edit.text().strip()
        if not input_text:
            QMessageBox.warning(self, "提示", self._missing_input_message())
            return
        if not output_text:
            QMessageBox.warning(self, "提示", "请选择输出文件夹")
            return

        input_mode = self._input_mode_for(self._selected_type)
        input_path = Path(input_text)
        if input_mode == "files":
            input_files = [Path(path) for path in self.selected_input_files()]
            invalid_files = [
                path for path in input_files
                if not path.is_file() or path.suffix.lower() not in {".xls", ".xlsx"}
            ]
            if not input_files or invalid_files:
                QMessageBox.warning(self, "提示", "请选择一个或多个有效的 .xls 或 .xlsx 清洗结果文件")
                return
        elif input_mode == "file":
            if not input_path.is_file() or input_path.suffix.lower() not in {".xls", ".xlsx"}:
                QMessageBox.warning(self, "提示", "请选择一个有效的 .xls 或 .xlsx 良率文件")
                return
        elif not input_path.is_dir():
            QMessageBox.warning(self, "提示", "请选择一个有效的输入文件夹")
            return

        output_path = Path(output_text)
        if output_path.exists() and not output_path.is_dir():
            QMessageBox.warning(self, "提示", "输出路径必须是文件夹")
            return

        self.status_text.clear()
        if self._selected_type in self.scatter_supported_types:
            self._scatter_manifest_by_type.pop(self._selected_type, None)
            self.scatter_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.start_btn.setText("处理中...")

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
        self.start_btn.setText(self._action_text_for(self._selected_type))
        if success:
            result = getattr(self.worker, "result", None)
            manifest = getattr(result, "scatter_manifest", None)
            if manifest:
                manifest_path = Path(manifest).resolve()
                if manifest_path.is_file():
                    self._scatter_manifest_by_type[self._selected_type] = manifest_path
                    self.scatter_btn.setEnabled(True)
                    self.scatter_btn.setToolTip(str(manifest_path))
                    self._log("📊 散点图数据已准备完成，可点击“FT 散点图”")
                    msg += "\n\n散点图数据已准备完成，请点击“FT 散点图”。"
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def _on_error(self, err: str):
        self._log(f"❌ 错误: {err}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText(self._action_text_for(self._selected_type))
        QMessageBox.critical(self, "错误", err)

    def _open_scatter(self):
        manifest = self._scatter_manifest_by_type.get(self._selected_type)
        if not manifest or not manifest.is_file():
            QMessageBox.warning(self, "提示", "请先完成一次日月新 DC 数据清洗")
            return
        try:
            from gui.scatter_launcher import launch_ft_scatter

            url = launch_ft_scatter(manifest)
            self._log(f"已打开 FT 散点图: {url}")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "散点图启动失败",
                f"{exc}\n\n请确认已安装 requirements.txt 中的 Streamlit 和 Plotly。",
            )

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{ts}] {msg}")
        sb = self.status_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_default_paths(self, input_path: str, output_path: str):
        self.input_edit.setText(input_path)
        self.output_edit.setText(output_path)
        if self._selected_type:
            self._path_state[self._selected_type] = (input_path, output_path)

    def _input_mode_for(self, data_type: str) -> str:
        if data_type in self.pat_analysis_types or data_type == "PAT":
            return "files"
        return "file" if data_type in self.yield_analysis_types or data_type == "SYL&SBL" else "directory"

    def selected_input_files(self) -> list[str]:
        """Return one or more full paths entered or selected for PAT."""
        text = self.input_edit.text().strip()
        if not text:
            return []
        return [part.strip() for part in text.split(MULTI_FILE_SEPARATOR) if part.strip()]

    def _default_paths_for_type(self, data_type: str) -> tuple[str, str]:
        desktop = str(Path.home() / "Desktop")
        input_path = "" if self._input_mode_for(data_type) in {"file", "files"} else (self.default_input or desktop)
        return input_path, self.default_output or desktop

    def _apply_operation_ui(self, data_type: str):
        if not data_type or not hasattr(self, "input_label"):
            return
        if data_type in self.pat_analysis_types or data_type == "PAT":
            self.input_label.setText("清洗结果文件:")
            self.input_edit.setPlaceholderText("选择一个或多个 DC/DVDS/RG 清洗结果 Excel 文件...")
            self.input_browse_btn.setText("选择文件...")
        elif self._input_mode_for(data_type) == "file":
            self.input_label.setText("良率文件:")
            self.input_edit.setPlaceholderText("选择一个 .xls 或 .xlsx 良率文件...")
            self.input_browse_btn.setText("选择文件...")
        else:
            self.input_label.setText("原始数据文件夹:")
            self.input_edit.setPlaceholderText("选择原始数据文件夹...")
            self.input_browse_btn.setText("选择文件夹...")
        if hasattr(self, "start_btn"):
            self.start_btn.setText(self._action_text_for(data_type))
        if hasattr(self, "scatter_btn"):
            supported = data_type in self.scatter_supported_types
            self.scatter_btn.setVisible(supported)
            self.scatter_btn.setEnabled(
                supported and data_type in self._scatter_manifest_by_type
            )

    def _action_text_for(self, data_type: str) -> str:
        if data_type in self.pat_analysis_types or data_type == "PAT":
            return "生成 PAT"
        if self._input_mode_for(data_type) == "file":
            return "生成 SYL&SBL"
        return "开始清洗"

    def _missing_input_message(self) -> str:
        if self._input_mode_for(self._selected_type) == "file":
            return "请选择良率 Excel 文件"
        if self._selected_type in self.pat_analysis_types or self._selected_type == "PAT":
            return "请选择一个或多个清洗结果 Excel 文件"
        return "请选择原始数据文件夹"
