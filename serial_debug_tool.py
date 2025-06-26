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
        # --- MODIFICATION 1: Update window title ---
        self.root.title("上大复旦上位机 - HEX模式 (12位ADC 3.0V参考电压)")
        self.root.geometry("800x600")
        
        self.serial_port = None
        self.receive_thread = None
        self.is_running = False
        
        # --- MODIFICATION 2: Add a byte buffer ---
        # This buffer will store incoming bytes until we have a complete 2-byte packet
        self.byte_buffer = b''
        
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
        
        # (UI code for settings is unchanged, so it's omitted for brevity)
        # ... [The UI setup code from your original file goes here] ...
        ttk.Label(settings_frame, text="端口:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(settings_frame, textvariable=self.port_var, width=15)
        self.port_combo.grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="刷新", command=self.refresh_ports).grid(row=0, column=2, padx=5)
        ttk.Label(settings_frame, text="波特率:").grid(row=0, column=3, padx=5)
        self.baudrate_var = tk.StringVar(value="115200")
        baudrate_combo = ttk.Combobox(settings_frame, textvariable=self.baudrate_var, width=10)
        baudrate_combo['values'] = ('1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200')
        baudrate_combo.grid(row=0, column=4, padx=5)
        ttk.Label(settings_frame, text="数据位:").grid(row=0, column=5, padx=5)
        self.databits_var = tk.StringVar(value="8")
        databits_combo = ttk.Combobox(settings_frame, textvariable=self.databits_var, width=5)
        databits_combo['values'] = ('5', '6', '7', '8')
        databits_combo.grid(row=0, column=6, padx=5)
        ttk.Label(settings_frame, text="停止位:").grid(row=1, column=0, padx=5)
        self.stopbits_var = tk.StringVar(value="1")
        stopbits_combo = ttk.Combobox(settings_frame, textvariable=self.stopbits_var, width=5)
        stopbits_combo['values'] = ('1', '1.5', '2')
        stopbits_combo.grid(row=1, column=1, padx=5)
        ttk.Label(settings_frame, text="校验位:").grid(row=1, column=3, padx=5)
        self.parity_var = tk.StringVar(value="无")
        parity_combo = ttk.Combobox(settings_frame, textvariable=self.parity_var, width=10)
        parity_combo['values'] = ('无', '奇校验', '偶校验')
        parity_combo.grid(row=1, column=4, padx=5)
        self.open_btn = ttk.Button(settings_frame, text="打开串口", command=self.toggle_serial)
        self.open_btn.grid(row=1, column=6, padx=5, pady=5)

        # 接收区域
        receive_frame = ttk.LabelFrame(main_frame, text="接收区域 (12-bit HEX + 电压计算)", padding="5")
        receive_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        receive_frame.columnconfigure(0, weight=1)
        receive_frame.rowconfigure(0, weight=1)
        self.receive_text = scrolledtext.ScrolledText(receive_frame, height=10, wrap=tk.WORD)
        self.receive_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        receive_btn_frame = ttk.Frame(receive_frame)
        receive_btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(receive_btn_frame, text="清空接收", command=self.clear_receive).pack(side=tk.LEFT, padx=5)

        # 发送区域
        send_frame = ttk.LabelFrame(main_frame, text="发送区域 (HEX)", padding="5")
        send_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        send_frame.columnconfigure(0, weight=1)
        send_frame.rowconfigure(0, weight=1)
        self.send_text = scrolledtext.ScrolledText(send_frame, height=5, wrap=tk.WORD)
        self.send_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.send_text.insert(1.0, "01 02 03 04 05")
        send_btn_frame = ttk.Frame(send_frame)
        send_btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(send_btn_frame, text="发送", command=self.send_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(send_btn_frame, text="清空发送", command=self.clear_send).pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar(value="串口未连接")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
    
    def refresh_ports(self):
        """
        Refreshes the list of available COM ports and sets the default
        to a port containing 'CH340' in its description, if found.
        """
        try:
            # 1. Get a list of all available serial ports
            ports = serial.tools.list_ports.comports()
            
            # 2. Format them into a list of strings for the combobox
            port_list = [f"{port.device} - {port.description}" for port in ports]
            
            # 3. Update the combobox with the new list
            self.port_combo['values'] = port_list
            
            # 4. If no ports are found, there's nothing more to do
            if not port_list:
                self.port_var.set("") # Clear the selection if no ports
                return

            # --- NEW LOGIC TO FIND AND SET DEFAULT PORT ---
            
            # 5. Search for a port with 'CH340' in its description
            ch340_index = -1
            for i, port_desc in enumerate(port_list):
                # We use .lower() to make the search case-insensitive (e.g., matches 'CH340', 'ch340', etc.)
                if "ch340" in port_desc.lower():
                    ch340_index = i
                    break # Found the first CH340 port, stop searching

            # 6. Set the combobox selection
            if ch340_index != -1:
                # If a CH340 port was found, set it as the default
                self.port_combo.current(ch340_index)
            else:
                # If no CH340 port was found, fall back to the original behavior: select the first port
                self.port_combo.current(0)

        except Exception as e:
            # It's good practice to handle potential errors during port listing
            messagebox.showerror("刷新端口错误", f"无法获取端口列表: {e}")
            
    def toggle_serial(self):
        if self.serial_port and self.serial_port.is_open: self.close_serial()
        else: self.open_serial()
    def open_serial(self):
        try:
            port_str = self.port_var.get()
            if not port_str: messagebox.showerror("错误", "请选择串口"); return
            port = port_str.split(" - ")[0]
            baudrate = int(self.baudrate_var.get())
            databits = int(self.databits_var.get())
            stopbits = float(self.stopbits_var.get())
            parity_map = {'无': serial.PARITY_NONE, '奇校验': serial.PARITY_ODD, '偶校验': serial.PARITY_EVEN}
            parity = parity_map[self.parity_var.get()]
            self.serial_port = serial.Serial(port=port, baudrate=baudrate, bytesize=databits, stopbits=stopbits, parity=parity, timeout=0.1)
            self.is_running = True
            self.open_btn.config(text="关闭串口")
            self.status_var.set(f"串口已连接: {port}")
            self.receive_thread = threading.Thread(target=self.receive_data, daemon=True)
            self.receive_thread.start()
        except Exception as e:
            messagebox.showerror("错误", f"打开串口失败: {str(e)}")
    def close_serial(self):
        try:
            self.is_running = False
            if self.receive_thread: self.receive_thread.join(timeout=1)
            if self.serial_port and self.serial_port.is_open: self.serial_port.close()
            self.open_btn.config(text="打开串口")
            self.status_var.set("串口未连接")
        except Exception as e:
            messagebox.showerror("错误", f"关闭串口失败: {str(e)}")

    # --- MODIFICATION 3: Overhaul the receive and process logic ---
    def receive_data(self):
        """Receiving thread: reads data and puts it into the buffer."""
        while self.is_running and self.serial_port and self.serial_port.is_open:
            try:
                # Read all available data from serial port
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    self.byte_buffer += data
                    
                    # Schedule the processing function to run in the main thread
                    self.root.after(0, self.process_and_display_data)
                    
                time.sleep(0.01)
                
            except Exception as e:
                if self.is_running:
                    self.root.after(0, lambda: messagebox.showerror("错误", f"接收数据失败: {str(e)}"))
                break

    def process_and_display_data(self):
        """
        Processes the byte buffer to find framed packets, construct 12-bit numbers, 
        and update the UI. This version includes a sync header for robust framing.
        This function runs in the main GUI thread.
        """
        # --- NEW LOGIC WITH FRAME SYNC ---
        
        # Define the sync header byte. This must match what the hardware sends.
        SYNC_HEADER = b'\xFF' # We use 0xFF as the header. b'' makes it a bytes object.
        PACKET_LENGTH = 3      # Total packet length: 1 header byte + 2 data bytes

        while True:
            # 1. Find the sync header in our buffer
            header_index = self.byte_buffer.find(SYNC_HEADER)

            # If no header is found, we can't process anything yet.
            if header_index == -1:
                # Optional: If buffer is very large, trim it to prevent infinite growth
                # in case of continuous bad data. Keep last few bytes in case header
                # is split across reads.
                if len(self.byte_buffer) > PACKET_LENGTH:
                     self.byte_buffer = self.byte_buffer[-(PACKET_LENGTH-1):]
                break # Exit the loop for now, wait for more data

            # 2. If header is found, discard any garbage data before it.
            if header_index > 0:
                self.byte_buffer = self.byte_buffer[header_index:]

            # 3. Check if we have a full packet (header + data)
            if len(self.byte_buffer) < PACKET_LENGTH:
                # We have a header but not enough data yet. Wait for the next read.
                break # Exit the loop for now

            # 4. We have a full packet. Extract and process it.
            # Packet structure: [Header (1 byte), High Byte (1 byte), Low Byte (1 byte)]
            high_byte = self.byte_buffer[1]
            low_byte = self.byte_buffer[2]

            # Reconstruct the 12-bit value.
            adc_value = (high_byte << 8) | low_byte

            # Calculate voltage
            voltage = (adc_value / 4095.0) * 2.998
            
            # Format for display
            timestamp = time.strftime("%H:%M:%S")
            display_str = (
                f"[{timestamp}] RX: {high_byte:02X} {low_byte:02X} -> "
                f"0x{adc_value:03X} ({adc_value}) -> {voltage:.3f}V\n"
            )
            self.receive_text.insert(tk.END, display_str)
            
            # 5. Remove the processed packet from the buffer and loop again
            #    to process any other complete packets in the buffer.
            self.byte_buffer = self.byte_buffer[PACKET_LENGTH:]
        
        self.receive_text.see(tk.END)

    # --- The send and clear methods are unchanged ---
    # ... [send_data, clear_receive, clear_send, on_closing] ...
    def send_data(self):
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showerror("错误", "请先打开串口")
            return
        try:
            hex_str = self.send_text.get(1.0, tk.END).strip()
            if not hex_str: return
            hex_str = re.sub(r'[^0-9A-Fa-f]', '', hex_str)
            if len(hex_str) % 2 != 0:
                messagebox.showerror("错误", "十六进制数据长度必须为偶数")
                return
            data = bytes.fromhex(hex_str)
            self.serial_port.write(data)
            formatted_hex = ' '.join([f'{byte:02X}' for byte in data])
            timestamp = time.strftime("%H:%M:%S")
            self.receive_text.insert(tk.END, f"[{timestamp}] TX: {formatted_hex}\n")
            self.receive_text.see(tk.END)
        except Exception as e:
            messagebox.showerror("错误", f"发送数据失败: {str(e)}")
            
    def clear_receive(self):
        self.receive_text.delete(1.0, tk.END)
        
    def clear_send(self):
        self.send_text.delete(1.0, tk.END)
        
    def on_closing(self):
        self.close_serial()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = SerialDebugTool(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()