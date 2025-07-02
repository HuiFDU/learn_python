# 文件名: main_window.py (Rev 2.3 - 最终界面)
# 文件名: main_window.py (Rev 2.5 - 新增CH3显示区)

import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QComboBox, QPushButton, QGridLayout, QLabel, QLineEdit, QTextEdit, QFrame)
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtGui import QFont

import serial.tools.list_ports
from data_processor import DataProcessor


MAX_LOG_LINES = 50
TRIM_LOG_LINES = 10

class MainWindow(QMainWindow):
    # ... (__init__ 和其他函数不变, 除了 setup_display 和 update_displays) ...
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hui & Rongrong & Gemini 的ADC监控上位机")
        self.setGeometry(100, 100, 600, 550) # 高度再增加一点

        # ... (日志、线程初始化不变) ...
        if not os.path.exists("log"):
            os.makedirs("log")

        self.processor = DataProcessor()
        self.processor.data_updated.connect(self.update_displays)
        self.processor.debug_message.connect(self.log_message)

        # --- UI 控件 ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.setup_serial_controls()
        self.setup_display_area()
        self.setup_debug_console()
        
        self.refresh_ports()
        self.print_startup_message()

    # --- [核心修改] 增加CH3的显示区域 ---
    def setup_display_area(self):
        """创建O1, O2, CH3的显示区域"""
        grid_layout = QGridLayout()
        grid_layout.setColumnStretch(1, 1)

        # --- O2 (Temperature) - CH1 ---
        o2_label = QLabel("O2 Sensor (CH1)")
        o2_label.setFont(QFont("Arial", 12, QFont.Bold))
        grid_layout.addWidget(o2_label, 0, 0, 1, 3)
        grid_layout.addWidget(QLabel("  Voltage:"), 1, 0)
        self.display_o2_voltage = QLineEdit("-.---")
        self.display_o2_voltage.setReadOnly(True); self.display_o2_voltage.setFont(QFont("Consolas", 12))
        grid_layout.addWidget(self.display_o2_voltage, 1, 1)
        grid_layout.addWidget(QLabel("V"), 1, 2)
        grid_layout.addWidget(QLabel("  Temperature:"), 2, 0)
        self.display_o2_temp = QLineEdit("---.-")
        self.display_o2_temp.setReadOnly(True); self.display_o2_temp.setFont(QFont("Consolas", 12))
        grid_layout.addWidget(self.display_o2_temp, 2, 1)
        grid_layout.addWidget(QLabel("℃"), 2, 2)

        # --- 分隔线 ---
        line1 = QFrame(); line1.setFrameShape(QFrame.HLine); line1.setFrameShadow(QFrame.Sunken)
        grid_layout.addWidget(line1, 3, 0, 1, 3)

        # --- O1 (Pressure) - CH2 ---
        o1_label = QLabel("O1 Sensor (CH2)")
        o1_label.setFont(QFont("Arial", 12, QFont.Bold))
        grid_layout.addWidget(o1_label, 4, 0, 1, 3)
        grid_layout.addWidget(QLabel("  Voltage:"), 5, 0)
        self.display_o1_voltage = QLineEdit("-.---")
        self.display_o1_voltage.setReadOnly(True); self.display_o1_voltage.setFont(QFont("Consolas", 12))
        grid_layout.addWidget(self.display_o1_voltage, 5, 1)
        grid_layout.addWidget(QLabel("V"), 5, 2)
        grid_layout.addWidget(QLabel("  Pressure:"), 6, 0)
        self.display_o1_pressure = QLineEdit("---.-")
        self.display_o1_pressure.setReadOnly(True); self.display_o1_pressure.setFont(QFont("Consolas", 12))
        grid_layout.addWidget(self.display_o1_pressure, 6, 1)
        grid_layout.addWidget(QLabel("KPa"), 6, 2)

        # --- [新增] CH3 显示区域 ---
        line2 = QFrame(); line2.setFrameShape(QFrame.HLine); line2.setFrameShadow(QFrame.Sunken)
        grid_layout.addWidget(line2, 7, 0, 1, 3)
        
        ch3_label = QLabel("数字通道-显示")
        ch3_label.setFont(QFont("Arial", 12, QFont.Bold))
        grid_layout.addWidget(ch3_label, 8, 0, 1, 3)
        
        grid_layout.addWidget(QLabel("  Pressure:"), 9, 0)
        self.display_ch3_pressure = QLineEdit("-----")
        self.display_ch3_pressure.setReadOnly(True); self.display_ch3_pressure.setFont(QFont("Consolas", 12))
        grid_layout.addWidget(self.display_ch3_pressure, 9, 1)
        grid_layout.addWidget(QLabel("KPa"), 9, 2)
        
        grid_layout.addWidget(QLabel("  Temperature:"), 10, 0)
        self.display_ch3_temp = QLineEdit("---.-")
        self.display_ch3_temp.setReadOnly(True); self.display_ch3_temp.setFont(QFont("Consolas", 12))
        grid_layout.addWidget(self.display_ch3_temp, 10, 1)
        grid_layout.addWidget(QLabel("℃"), 10, 2)

        self.main_layout.addLayout(grid_layout)

    # --- [核心修改] 更新槽函数以处理CH3数据 ---
    @pyqtSlot(dict)
    def update_displays(self, data):
        """更新UI上的所有显示"""
        # 更新O2
        if 'o2_voltage' in data and 'o2_temperature' in data:
            self.display_o2_voltage.setText(f"{data['o2_voltage']:.3f}")
            self.display_o2_temp.setText(f"{data['o2_temperature']:.1f}")
        
        # 更新O1
        if 'o1_voltage' in data and 'o1_pressure' in data:
            self.display_o1_voltage.setText(f"{data['o1_voltage']:.3f}")
            self.display_o1_pressure.setText(f"{data['o1_pressure']:.1f}")
        
        # 更新CH3
        if 'ch3_pressure' in data and 'ch3_temperature' in data:
            self.display_ch3_pressure.setText(f"{data['ch3_pressure']:.0f}")
            self.display_ch3_temp.setText(f"{data['ch3_temperature']:.1f}")

    # ... (其他所有函数保持不变) ...
    def setup_serial_controls(self,):
        #... no change
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
    
    def setup_debug_console(self,):
        #... no change
        self.debug_console = QTextEdit()
        self.debug_console.setReadOnly(True)
        self.debug_console.setFont(QFont("Consolas", 10))
        self.main_layout.addWidget(QLabel("调试信息:"))
        self.main_layout.addWidget(self.debug_console)

    def refresh_ports(self,):
        #... no change
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
        #... no change
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

    def log_message(self, message):
        #... no change
        if self.debug_console.document().blockCount() > MAX_LOG_LINES:
            self.archive_log()
        self.debug_console.append(message)
        self.debug_console.verticalScrollBar().setValue(self.debug_console.verticalScrollBar().maximum())
    
    def archive_log(self,):
        #... no change
        import os, datetime
        from PyQt5.QtGui import QTextCursor
        LOG_DIR = "log"
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
            self.log_message(f"--- [系统] 旧日志已归档至: {filepath} ---")
        except IOError as e:
            self.log_message(f"--- [错误] 归档日志失败: {e} ---")
        cursor.removeSelectedText()
        cursor.deleteChar()
        
    def print_startup_message(self,):
        #... no change
        import datetime
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y年%m月%d日, %H点%M分%S秒")
        self.log_message(f"现在是{timestamp}，系统启动完成，等待下一步指令。")
        self.log_message("="*50)
        
    def closeEvent(self, event):
        #... no change
        self.processor.stop_processing()
        event.accept()