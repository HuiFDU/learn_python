# 文件名: main_window.py (Rev 2.2 - 递归修复)

# ... (import部分和常量定义保持不变) ...
import sys
import os
import datetime 
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QComboBox, QPushButton, QGridLayout, QLabel, QLineEdit, QTextEdit)
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtGui import QFont, QTextCursor
import serial.tools.list_ports
from data_processor import DataProcessor

MAX_LOG_LINES = 50
TRIM_LOG_LINES = 10
LOG_DIR = "log"

class MainWindow(QMainWindow):
    # ... (__init__ 和其他大部分函数保持不变) ...
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hui & Rongrong & Gemini 的ADC监控上位机")
        self.setGeometry(100, 100, 600, 500)
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        self.processor = DataProcessor()
        self.processor.data_updated.connect(self.update_voltage_displays)
        self.processor.debug_message.connect(self.log_message)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.setup_serial_controls()
        self.setup_voltage_grid()
        self.setup_debug_console()
        self.refresh_ports()
        self.print_startup_message()

    def print_startup_message(self):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y年%m月%d日, %H点%M分%S秒")
        # 直接调用log_message，这是安全的，因为它只在启动时运行一次
        self.log_message(f"现在是{timestamp}，系统启动完成，等待下一步指令。")
        self.log_message("="*50)

    def setup_serial_controls(self):
        layout = QHBoxLayout()
        self.port_combobox = QComboBox()
        self.port_combobox.setMinimumWidth(300)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button = QPushButton("连接")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(self.toggle_connection)
        layout.addWidget(QLabel("串口:"))
        layout.addWidget(self.port_combobox)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.connect_button)
        layout.addStretch()
        self.main_layout.addLayout(layout)

    def setup_voltage_grid(self):
        grid_layout = QGridLayout()
        self.voltage_displays = []
        for i in range(8):
            channel_label = QLabel(f"CH{i+1} Voltage:")
            voltage_display = QLineEdit("0.000 V")
            voltage_display.setReadOnly(True)
            voltage_display.setFont(QFont("Consolas", 12))
            voltage_display.setMinimumWidth(120)
            row = i % 4
            col = (i // 4) * 2
            grid_layout.addWidget(channel_label, row, col)
            grid_layout.addWidget(voltage_display, row, col + 1)
            self.voltage_displays.append(voltage_display)
        self.main_layout.addLayout(grid_layout)

    def setup_debug_console(self):
        self.debug_console = QTextEdit()
        self.debug_console.setReadOnly(True)
        self.debug_console.setFont(QFont("Consolas", 10))
        self.main_layout.addWidget(QLabel("调试信息:"))
        self.main_layout.addWidget(self.debug_console)

    def refresh_ports(self):
        self.port_combobox.clear()
        ports = serial.tools.list_ports.comports()
        ch340_port_device = None
        if not ports:
            self.port_combobox.addItem("未找到串口设备")
            self.port_combobox.setEnabled(False)
            return
        self.port_combobox.setEnabled(True)
        for port in ports:
            display_text = port.description
            self.port_combobox.addItem(display_text, port.device)
            if "ch340" in port.description.lower():
                ch340_port_device = port.device
        if ch340_port_device:
            index = self.port_combobox.findData(ch340_port_device)
            if index != -1:
                self.port_combobox.setCurrentIndex(index)
                self.log_message(f"[智能选择] 已自动选择CH340端口: {self.port_combobox.itemText(index)}")

    def toggle_connection(self, checked):
        if checked:
            port = self.port_combobox.currentData() 
            if not port:
                self.log_message("[错误] 未选择任何有效串口。")
                self.connect_button.setChecked(False)
                return
            self.connect_button.setText("断开")
            self.port_combobox.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.processor.start_processing(port)
        else:
            self.connect_button.setText("连接")
            self.port_combobox.setEnabled(True)
            self.refresh_button.setEnabled(True)
            self.processor.stop_processing()

    @pyqtSlot(list)
    def update_voltage_displays(self, voltages):
        for i, voltage in enumerate(voltages):
            self.voltage_displays[i].setText(f"{voltage:.3f} V")
    
    # --- [核心修改] 分离职责 ---

    @pyqtSlot(str)
    def log_message(self, message):
        """
        这是“看门人”函数。它负责检查是否需要归档，
        然后调用简单的显示函数来添加消息。
        """
        # 1. 检查是否需要归档
        if self.debug_console.document().blockCount() > MAX_LOG_LINES:
            self.archive_log()

        # 2. 调用简单的显示函数来添加原始消息
        self._add_log_to_display(message)

    def _add_log_to_display(self, message):
        """
        这是简单的“执行者”函数。它的唯一职责是向UI添加文本。
        它不包含任何检查逻辑。
        """
        self.debug_console.append(message)
        self.debug_console.verticalScrollBar().setValue(self.debug_console.verticalScrollBar().maximum())

    def archive_log(self):
        """将旧的日志内容归档到文件，并从UI中移除"""
        now = datetime.datetime.now()
        filename = now.strftime("%Y%m%d_%H%M%S") + ".txt"
        filepath = os.path.join(LOG_DIR, filename)

        cursor = QTextCursor(self.debug_console.document())
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, TRIM_LOG_LINES)
        
        text_to_archive = cursor.selection().toPlainText()

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"--- Log archive from {now.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(text_to_archive)
            
            # [核心修改] 直接调用简单的显示函数来报告状态，打破递归！
            self._add_log_to_display(f"--- [系统] 旧日志已归档至: {filepath} ---")

        except IOError as e:
            self._add_log_to_display(f"--- [错误] 归档日志失败: {e} ---")

        cursor.removeSelectedText()
        cursor.deleteChar()

    def closeEvent(self, event):
        self.processor.stop_processing()
        event.accept()