#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import re


class SerialDebugTool:
    def __init__(self, root):
        self.root = root
        self.root.title("串口调试助手 - HEX模式 (8位ADC 3.0V参考电压)")
        self.root.geometry("800x600")
        
        self.serial_port = None
        self.receive_thread = None
        self.is_running = False
        
        self.setup_ui()
        self.refresh_ports()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置行列权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 串口设置区域
        settings_frame = ttk.LabelFrame(main_frame, text="串口设置", padding="5")
        settings_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 端口选择
        ttk.Label(settings_frame, text="端口:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(settings_frame, textvariable=self.port_var, width=15)
        self.port_combo.grid(row=0, column=1, padx=5)
        
        # 刷新端口按钮
        ttk.Button(settings_frame, text="刷新", command=self.refresh_ports).grid(row=0, column=2, padx=5)
        
        # 波特率
        ttk.Label(settings_frame, text="波特率:").grid(row=0, column=3, padx=5)
        self.baudrate_var = tk.StringVar(value="115200")
        baudrate_combo = ttk.Combobox(settings_frame, textvariable=self.baudrate_var, width=10)
        baudrate_combo['values'] = ('1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200')
        baudrate_combo.grid(row=0, column=4, padx=5)
        
        # 数据位
        ttk.Label(settings_frame, text="数据位:").grid(row=0, column=5, padx=5)
        self.databits_var = tk.StringVar(value="8")
        databits_combo = ttk.Combobox(settings_frame, textvariable=self.databits_var, width=5)
        databits_combo['values'] = ('5', '6', '7', '8')
        databits_combo.grid(row=0, column=6, padx=5)
        
        # 停止位
        ttk.Label(settings_frame, text="停止位:").grid(row=1, column=0, padx=5)
        self.stopbits_var = tk.StringVar(value="1")
        stopbits_combo = ttk.Combobox(settings_frame, textvariable=self.stopbits_var, width=5)
        stopbits_combo['values'] = ('1', '1.5', '2')
        stopbits_combo.grid(row=1, column=1, padx=5)
        
        # 校验位
        ttk.Label(settings_frame, text="校验位:").grid(row=1, column=3, padx=5)
        self.parity_var = tk.StringVar(value="无")
        parity_combo = ttk.Combobox(settings_frame, textvariable=self.parity_var, width=10)
        parity_combo['values'] = ('无', '奇校验', '偶校验')
        parity_combo.grid(row=1, column=4, padx=5)
        
        # 打开/关闭串口按钮
        self.open_btn = ttk.Button(settings_frame, text="打开串口", command=self.toggle_serial)
        self.open_btn.grid(row=1, column=6, padx=5, pady=5)
        
        # 接收区域
        receive_frame = ttk.LabelFrame(main_frame, text="接收区域 (HEX + 电压计算)", padding="5")
        receive_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        receive_frame.columnconfigure(0, weight=1)
        receive_frame.rowconfigure(0, weight=1)
        
        # 接收文本框
        self.receive_text = scrolledtext.ScrolledText(receive_frame, height=10, wrap=tk.WORD)
        self.receive_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 接收区按钮
        receive_btn_frame = ttk.Frame(receive_frame)
        receive_btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(receive_btn_frame, text="清空接收", command=self.clear_receive).pack(side=tk.LEFT, padx=5)
        
        # 发送区域
        send_frame = ttk.LabelFrame(main_frame, text="发送区域 (HEX)", padding="5")
        send_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        send_frame.columnconfigure(0, weight=1)
        send_frame.rowconfigure(0, weight=1)
        
        # 发送文本框
        self.send_text = scrolledtext.ScrolledText(send_frame, height=5, wrap=tk.WORD)
        self.send_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.send_text.insert(1.0, "01 02 03 04 05")  # 示例数据
        
        # 发送区按钮
        send_btn_frame = ttk.Frame(send_frame)
        send_btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(send_btn_frame, text="发送", command=self.send_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(send_btn_frame, text="清空发送", command=self.clear_send).pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar(value="串口未连接")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
    def refresh_ports(self):
        """刷新可用串口列表"""
        ports = serial.tools.list_ports.comports()
        port_list = []
        ch340_ports = []
        other_ports = []
        
        for port in ports:
            port_desc = f"{port.device} - {port.description}"
            if "CH340" in port.description.upper():
                ch340_ports.append(port_desc)
            else:
                other_ports.append(port_desc)
        
        # CH340端口优先显示
        port_list = ch340_ports + other_ports
        
        self.port_combo['values'] = port_list
        if port_list:
            self.port_combo.current(0)
            
    def toggle_serial(self):
        """打开/关闭串口"""
        if self.serial_port and self.serial_port.is_open:
            self.close_serial()
        else:
            self.open_serial()
            
    def open_serial(self):
        """打开串口"""
        try:
            port_str = self.port_var.get()
            if not port_str:
                messagebox.showerror("错误", "请选择串口")
                return
                
            # 提取端口名
            port = port_str.split(" - ")[0]
            
            # 获取参数
            baudrate = int(self.baudrate_var.get())
            databits = int(self.databits_var.get())
            stopbits = float(self.stopbits_var.get())
            
            # 校验位映射
            parity_map = {
                '无': serial.PARITY_NONE,
                '奇校验': serial.PARITY_ODD,
                '偶校验': serial.PARITY_EVEN
            }
            parity = parity_map[self.parity_var.get()]
            
            # 打开串口
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=databits,
                stopbits=stopbits,
                parity=parity,
                timeout=0.1
            )
            
            self.is_running = True
            self.open_btn.config(text="关闭串口")
            self.status_var.set(f"串口已连接: {port}")
            
            # 启动接收线程
            self.receive_thread = threading.Thread(target=self.receive_data, daemon=True)
            self.receive_thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"打开串口失败: {str(e)}")
            
    def close_serial(self):
        """关闭串口"""
        try:
            self.is_running = False
            if self.receive_thread:
                self.receive_thread.join(timeout=1)
                
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                
            self.open_btn.config(text="打开串口")
            self.status_var.set("串口未连接")
            
        except Exception as e:
            messagebox.showerror("错误", f"关闭串口失败: {str(e)}")
            
    def receive_data(self):
        """接收数据线程"""
        while self.is_running and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    hex_data = ' '.join([f'{byte:02X}' for byte in data])
                    
                    # 在主线程中更新UI
                    self.root.after(0, self.update_receive_text, hex_data)
                    
                time.sleep(0.01)
                
            except Exception as e:
                if self.is_running:
                    self.root.after(0, lambda: messagebox.showerror("错误", f"接收数据失败: {str(e)}"))
                break
                
    def update_receive_text(self, data):
        """更新接收文本框"""
        timestamp = time.strftime("%H:%M:%S")
        self.receive_text.insert(tk.END, f"[{timestamp}] RX: {data}\n")
        
        # 计算并显示电压值（8位ADC，参考电压3.0V）
        try:
            hex_values = data.split()
            voltages = []
            for hex_val in hex_values:
                adc_value = int(hex_val, 16)  # 将十六进制转换为十进制
                voltage = (adc_value / 255.0) * 3.0  # 计算电压
                voltages.append(f"{voltage:.3f}V")
            
            voltage_str = " ".join(voltages)
            self.receive_text.insert(tk.END, f"            电压: {voltage_str}\n")
        except:
            pass  # 如果转换失败，忽略电压显示
            
        self.receive_text.see(tk.END)
        
    def send_data(self):
        """发送数据"""
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showerror("错误", "请先打开串口")
            return
            
        try:
            # 获取发送框中的文本
            hex_str = self.send_text.get(1.0, tk.END).strip()
            if not hex_str:
                return
                
            # 移除所有非十六进制字符
            hex_str = re.sub(r'[^0-9A-Fa-f]', '', hex_str)
            
            # 确保是偶数个字符
            if len(hex_str) % 2 != 0:
                messagebox.showerror("错误", "十六进制数据长度必须为偶数")
                return
                
            # 转换为字节
            data = bytes.fromhex(hex_str)
            
            # 发送数据
            self.serial_port.write(data)
            
            # 显示发送的数据
            formatted_hex = ' '.join([f'{byte:02X}' for byte in data])
            timestamp = time.strftime("%H:%M:%S")
            self.receive_text.insert(tk.END, f"[{timestamp}] TX: {formatted_hex}\n")
            self.receive_text.see(tk.END)
            
        except Exception as e:
            messagebox.showerror("错误", f"发送数据失败: {str(e)}")
            
    def clear_receive(self):
        """清空接收区"""
        self.receive_text.delete(1.0, tk.END)
        
    def clear_send(self):
        """清空发送区"""
        self.send_text.delete(1.0, tk.END)
        
    def on_closing(self):
        """关闭窗口时的处理"""
        self.close_serial()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = SerialDebugTool(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()