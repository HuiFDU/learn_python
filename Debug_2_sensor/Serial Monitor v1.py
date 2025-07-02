# HRG Serial Monitor v1.6
# Authors: Hui, Rongrong, Gemini
# Description: A GUI tool with refined UI and memory management for the debug log.
# v1.6 Changelog:
# - Implemented log rotation with archiving to CSV files.
# - Logs are saved in a 'log' subdirectory.
# - UI log is trimmed when it reaches a defined maximum number of lines.

# HRG Serial Monitor v1.7
# Authors: Hui, Rongrong, Gemini
# Description: A GUI tool with refined UI and memory management for the debug log.
# v1.7 Changelog:
# - Added a graceful exit handler to save all remaining log data upon closing the window.

# HRG Serial Monitor v1.8
# Authors: Hui, Rongrong, Gemini
# Description: A GUI tool with refined UI and memory management for the debug log.
# v1.8 Changelog:
# - Added a "Manual Save & Clear" button to save all current logs on demand.


import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog # ### 修改点 1: 导入filedialog ###
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import struct
from datetime import datetime
import os
import csv # 导入CSV模块

class HRG_SerialMonitor:
    # --- 修改点 1: 定义常量 ---
    UI_MAX_LINES = 800  # UI中日志的最大行数
    UI_TRIM_LINES = 600 # 达到最大行数后，归档并删除的行数
    LOG_SUBFOLDER = "log" # 日志存放的子文件夹名

    def __init__(self, root):
        self.root = root
        self.root.title("H.R.G. 实时采集系统（硅所调试用） v1.6")
        self.root.geometry("550x550")

        self.port_map = {}
        self.log_counter = 0

        # --- 新增: 为写入CSV文件准备的数据缓冲区 ---
        self.csv_buffer = []

        self.setup_logging_folder() # 确保log文件夹存在

        # ... [UI组件定义部分保持不变，这里省略以保持简洁] ...
        # --- 串口配置区 ---
        control_frame = ttk.LabelFrame(root, text="串口设置")
        control_frame.pack(padx=10, pady=10, fill="x")
        control_frame.columnconfigure(1, weight=1)

        ttk.Label(control_frame, text="串口:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combobox = ttk.Combobox(control_frame, textvariable=self.port_var, state="readonly")
        self.port_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(control_frame, text="波特率:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.baud_var = tk.StringVar(value='115200')
        self.baud_combobox = ttk.Combobox(control_frame, textvariable=self.baud_var, values=['9600', '19200', '38400', '57600', '115200'])
        self.baud_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.refresh_button = ttk.Button(control_frame, text="刷新串口", command=self.update_serial_ports)
        self.refresh_button.grid(row=0, column=2, padx=5, pady=5)

        action_frame = ttk.Frame(root)
        action_frame.pack(padx=10, pady=5, fill="x")
        self.toggle_button = ttk.Button(action_frame, text="开始采集", command=self.toggle_monitoring)
        self.toggle_button.pack(side="left", expand=True, fill="x", padx=5)
        
        self.status_var = tk.StringVar(value="状态: 已断开")
        self.status_label = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        self.status_label.pack(side="bottom", fill="x")

        data_frame = ttk.LabelFrame(root, text="实时数据")
        data_frame.pack(padx=10, pady=10, fill="x")
        data_frame.columnconfigure(0, weight=1)
        data_frame.columnconfigure(1, weight=1)
        
        pressure_sub_frame = ttk.Frame(data_frame)
        pressure_sub_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(pressure_sub_frame, text="压力 (KPa):", font=("Helvetica", 14)).pack()
        self.pressure_var = tk.StringVar(value="--")
        ttk.Label(pressure_sub_frame, textvariable=self.pressure_var, font=("Helvetica", 24, "bold"), foreground="blue").pack()

        temperature_sub_frame = ttk.Frame(data_frame)
        temperature_sub_frame.grid(row=0, column=1, sticky="nsew")
        ttk.Label(temperature_sub_frame, text="温度 (°C):", font=("Helvetica", 14)).pack()
        self.temperature_var = tk.StringVar(value="--")
        ttk.Label(temperature_sub_frame, textvariable=self.temperature_var, font=("Helvetica", 24, "bold"), foreground="red").pack()

        debug_frame = ttk.LabelFrame(root, text="采集日志 (自动归档清理)")
        debug_frame.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        self.debug_text = scrolledtext.ScrolledText(debug_frame, height=10, state='disabled')
        self.debug_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.serial_port = None
        self.is_monitoring = False
        self.monitoring_thread = None

        self.update_serial_ports()
    
    # --- 修改点 1: 绑定窗口关闭事件到我们的自定义函数 ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- 修改点 2: 创建处理关闭事件的新方法 ---
    def on_closing(self):
        """在窗口关闭前执行此函数。"""
        # 1. 停止监控线程，这会安全地关闭串口
        if self.is_monitoring:
            self.is_monitoring = False
            # 给予线程一点时间来完成当前循环，避免竞争条件
            # 对于这个应用，线程的time.sleep(1)和串口timeout足够，一般不需要额外等待
        
        # 2. 检查缓冲区是否有未保存的数据，并执行最终保存
        if self.csv_buffer:
            self.status_var.set("状态: 正在保存剩余日志...")
            self.root.update_idletasks() # 强制UI更新状态信息
            self.archive_log_data(is_final_save=True)
        
        # 3. 销毁主窗口，正式退出程序
        self.root.destroy()

    # --- 修改点 2: 新增方法，用于创建日志文件夹 ---
    def setup_logging_folder(self):
        """检查并创建用于存放日志的子文件夹。"""
        if not os.path.exists(self.LOG_SUBFOLDER):
            try:
                os.makedirs(self.LOG_SUBFOLDER)
            except OSError as e:
                # 在状态栏显示错误，而不是让程序崩溃
                self.status_var.set(f"状态: 错误, 无法创建log文件夹: {e}")

    def update_serial_ports(self):
        # ... 此函数无变化 ...
        self.port_map.clear()
        ports_info = serial.tools.list_ports.comports()
        display_names = []
        for port in ports_info:
            description_simple = port.description.split(' (')[0]
            display_name = f"{port.device}: {description_simple}"
            self.port_map[display_name] = port.device
            display_names.append(display_name)
        self.port_combobox['values'] = display_names
        preferred_port_display_name = None
        if display_names:
            for name in display_names:
                if 'CH340' in name.upper():
                    preferred_port_display_name = name
                    break
            if preferred_port_display_name:
                self.port_var.set(preferred_port_display_name)
            else:
                self.port_var.set(display_names[0])
        else:
            self.port_var.set("")

    def toggle_monitoring(self):
        # ... 此函数无变化 ...
        if not self.is_monitoring:
            selected_display_name = self.port_var.get()
            if not selected_display_name:
                self.status_var.set("状态: 错误, 未选择串口!")
                return
            port_device = self.port_map[selected_display_name]
            baud = int(self.baud_var.get())
            try:
                self.serial_port = serial.Serial(port_device, baud, timeout=0.5)
                self.is_monitoring = True
                self.log_counter = 0
                self.csv_buffer.clear() # 开始采集时清空缓冲区
                self.debug_text.config(state='normal')
                self.debug_text.delete('1.0', tk.END)
                self.debug_text.config(state='disabled')
                self.monitoring_thread = threading.Thread(target=self.serial_communication_loop, daemon=True)
                self.monitoring_thread.start()
                self.toggle_button.config(text="停止采集")
                self.status_var.set(f"状态: 正在采集 {selected_display_name}...")
                self.port_combobox.config(state="disabled")
                self.baud_combobox.config(state="disabled")
                self.refresh_button.config(state="disabled")
            except serial.SerialException:
                self.status_var.set(f"状态: 错误, 无法打开 {selected_display_name}")
                self.serial_port = None
        else:
            self.is_monitoring = False
            self.toggle_button.config(text="开始采集")
            self.status_var.set("状态: 已断开")
            self.pressure_var.set("--")
            self.temperature_var.set("--")
            self.port_combobox.config(state="readonly")
            self.baud_combobox.config(state="normal")
            self.refresh_button.config(state="normal")
            
            # 停止采集时，将缓冲区剩余的数据也保存一次
            if self.csv_buffer:
                self.archive_log_data(is_final_save=True)

    def serial_communication_loop(self):
        # ... 此函数无变化 ...
        command_to_send = bytes.fromhex('AF 01 FA')
        while self.is_monitoring:
            try:
                self.serial_port.write(command_to_send)
                response = self.serial_port.read(6)
                if len(response) == 6 and response.startswith(b'\xaf') and response.endswith(b'\xfa'):
                    self.parse_and_update_data(response)
                time.sleep(1)
            except serial.SerialException:
                def safe_stop():
                    self.status_var.set("状态: 串口通信错误, 已断开")
                    if self.is_monitoring:
                        self.toggle_monitoring()
                self.root.after(0, safe_stop)
                break
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

    def parse_and_update_data(self, data):
        try:
            pressure_raw = struct.unpack('>H', data[1:3])[0]
            pressure_kpa = pressure_raw
            temperature_raw = struct.unpack('>h', data[3:5])[0]
            temperature_c = temperature_raw / 10.0
            
            timestamp_dt = datetime.now() # 获取datetime对象，方便后续格式化
            
            # --- 修改点 3: 准备UI和CSV两种格式的数据 ---
            timestamp_str_ui = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
            log_message_ui = f"[{timestamp_str_ui}] 压力: {pressure_kpa:.2f} KPa,  温度: {temperature_c:.1f} °C\n"
            
            timestamp_str_csv = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            csv_row = [timestamp_str_csv, f"{pressure_kpa:.2f}", f"{temperature_c:.1f}"]

            self.root.after(0, self.update_gui_and_log, log_message_ui, csv_row, pressure_kpa, temperature_c)
        except Exception as e:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            error_message = f"[{timestamp}] 数据解析错误: {e}\n"
            self.root.after(0, self.append_to_debug_text, error_message) # 只更新UI

    def update_gui_and_log(self, ui_msg, csv_data_row, pressure, temperature):
        # 更新上方的实时数据标签
        self.pressure_var.set(f"{pressure:.2f}")
        self.temperature_var.set(f"{temperature:.1f}")
        
        # 将格式化好的日志消息追加到日志窗口
        self.append_to_debug_text(ui_msg)

        # --- 修改点 4: 将CSV数据行存入缓冲区 ---
        self.csv_buffer.append(csv_data_row)
        
    def append_to_debug_text(self, message):
        self.debug_text.config(state='normal')
        self.debug_text.insert(tk.END, message)
        self.log_counter += 1
        self.debug_text.see(tk.END)
        self.debug_text.config(state='disabled')
        
        # --- 修改点 5: 检查是否需要归档 ---
        if self.log_counter >= self.UI_MAX_LINES:
            self.archive_log_data()

    # --- 修改点 6: 全新的归档核心函数 ---
    def archive_log_data(self, is_final_save=False):
        """将缓冲区的数据写入CSV文件，并清理UI文本和缓冲区"""
        
        if is_final_save:
            # 如果是最后一次保存，则保存缓冲区所有内容
            lines_to_archive_count = len(self.csv_buffer)
        else:
            # 否则，按预设值保存
            lines_to_archive_count = self.UI_TRIM_LINES
            
        if lines_to_archive_count == 0:
            return

        # 1. 从缓冲区切片出要归档的数据
        data_to_write = self.csv_buffer[:lines_to_archive_count]
        
        # 2. 生成文件名并写入CSV
        try:
            # 文件名包含日期和时间，确保唯一性
            filename = f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(self.LOG_SUBFOLDER, filename)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入CSV表头
                writer.writerow(['Timestamp', 'Pressure (KPa)', 'Temperature (C)'])
                # 写入数据行
                writer.writerows(data_to_write)
            
            # 在状态栏提示用户已保存
            self.status_var.set(f"状态: 已归档 {lines_to_archive_count} 行至 {filename}")

        except Exception as e:
            self.status_var.set(f"状态: 错误, 写入日志文件失败: {e}")
            return # 如果写入失败，则不进行后续的清理操作，避免数据丢失

        # 3. 更新缓冲区（删除已写入的部分）
        self.csv_buffer = self.csv_buffer[lines_to_archive_count:]

        # 4. 如果不是最后一次保存，才清理UI
        if not is_final_save:
            self.debug_text.config(state='normal')
            # 删除UI中最旧的行
            self.debug_text.delete('1.0', f'{self.UI_TRIM_LINES + 1}.0')
            self.debug_text.config(state='disabled')
            self.log_counter -= self.UI_TRIM_LINES


if __name__ == "__main__":
    root = tk.Tk()
    app = HRG_SerialMonitor(root)
    root.mainloop()