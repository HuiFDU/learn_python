# HRG Serial Monitor v1.4
# Authors: Hui, Rongrong, Gemini
# Description: A GUI tool with refined UI and memory management for the debug log.
# v1.4 Changelog:
# - Simplified COM port display string (e.g., "COM5: USB-SERIAL CH340").
# - Implemented a log rotation in the debug window to prevent memory leaks.

import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import struct
from datetime import datetime

class HRG_SerialMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("H.R.G. 实时采集系统（硅所调试用） v1.4")
        self.root.geometry("550x550")

        self.port_map = {}
        # v1.4更新: 新增日志计数器，用于管理调试窗口内容
        self.log_counter = 0

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

        # ... 其他UI组件保持不变 ...
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

        debug_frame = ttk.LabelFrame(root, text="原始数据日志 (自动清理)")
        debug_frame.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        self.debug_text = scrolledtext.ScrolledText(debug_frame, height=10, state='disabled')
        self.debug_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.serial_port = None
        self.is_monitoring = False
        self.monitoring_thread = None

        self.update_serial_ports()
        
    def update_serial_ports(self):
        self.port_map.clear()
        ports_info = serial.tools.list_ports.comports()
        
        display_names = []
        for port in ports_info:
            # v1.4更新: 格式化显示名称，去除末尾的 "(COMx)"
            # port.description 通常是 "USB-SERIAL CH340 (COM5)"
            # 我们只取括号前的部分
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
        # ... 此函数逻辑不变 ...
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
                
                # v1.4更新: 重置日志计数器
                self.log_counter = 0
                self.debug_text.config(state='normal')
                self.debug_text.delete('1.0', tk.END) # 清空上次的日志
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

    def serial_communication_loop(self):
        # ... 此函数逻辑不变 ...
        command_to_send = bytes.fromhex('AF 01 FA')
        while self.is_monitoring:
            try:
                self.serial_port.write(command_to_send)
                response = self.serial_port.read(6)
                self.log_to_debug_window(response)
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

    def log_to_debug_window(self, data):
        # ... 此函数逻辑不变 ...
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        hex_string = ' '.join(f'{b:02X}' for b in data)
        log_message = f"[{timestamp}] 收← {hex_string}\n"
        self.root.after(0, self.append_to_debug_text, log_message)

    def append_to_debug_text(self, message):
        """
        v1.4更新: 在追加文本的同时，检查日志行数并执行清理。
        """
        self.debug_text.config(state='normal')
        self.debug_text.insert(tk.END, message)
        self.log_counter += 1

        # 当日志达到60行时，删除最旧的10行
        if self.log_counter >= 60:
            self.debug_text.delete('1.0', '11.0') # '1.0'是第1行, '11.0'是第11行的开头 (即删除10行)
            self.log_counter -= 10 # 更新计数器

        self.debug_text.see(tk.END) # 自动滚动到底部
        self.debug_text.config(state='disabled')

    def parse_and_update_data(self, data):
        # ... 此函数逻辑不变 ...
        pressure_raw = struct.unpack('>H', data[1:3])[0]
        pressure_kpa = pressure_raw
        temperature_raw = struct.unpack('>h', data[3:5])[0]
        temperature_c = temperature_raw / 10.0
        self.root.after(0, self.update_gui_labels, pressure_kpa, temperature_c)

    def update_gui_labels(self, pressure, temperature):
        # ... 此函数逻辑不变 ...
        self.pressure_var.set(f"{pressure:.2f}")
        self.temperature_var.set(f"{temperature:.1f}")


if __name__ == "__main__":
    root = tk.Tk()
    app = HRG_SerialMonitor(root)
    root.mainloop()