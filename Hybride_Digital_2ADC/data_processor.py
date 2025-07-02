# 文件名: data_processor.py (Rev 2.3 - 物理量计算)
# Hui & Rongrong & Gemini 合作开发版本
#
# Rev 2.3 修改:
# - 在解析电压后，直接计算出O1(压力)和O2(温度)的物理量。
# - data_updated 信号现在传递一个包含物理量字典。
# - 旧的voltages列表不再向主线程传递。

# 文件名: data_processor.py (Rev 2.5 - 解析CH3)
# Hui & Rongrong & Gemini 合作开发版本
#
# Rev 2.5 修改:
# - 在协议解析中，增加了对CH3新格式包的完整解析。
# - data_updated 信号传递的字典中，现在新增了 ch3_pressure 和 ch3_temperature。

import serial
import serial.tools.list_ports
import time
from PyQt5.QtCore import QThread, pyqtSignal
import struct # 引入struct库来处理有符号数

# ... (常量定义不变) ...
NEW_FRAME_TOTAL_BYTES = 16
V_REF = 3.0
SOF = 0xAF
EOF = 0xFA

class DataProcessor(QThread):
    # 信号和 __init__ 等保持不变
    data_updated = pyqtSignal(dict)
    debug_message = pyqtSignal(str)
    
    # ... (start/stop/linear_map 等函数不变) ...
    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = serial.Serial()
        self.port_name = ""
        self.running = False
        self._state = "HUNTING"

    def start_processing(self, port_name):
        if self.isRunning(): return
        self.port_name = port_name
        self.running = True
        self._state = "HUNTING"
        self.start()

    def stop_processing(self):
        self.running = False
        self.wait()

    def linear_map(self, value, from_min, from_max, to_min, to_max):
        if (from_max - from_min) == 0: return to_min
        normalized_value = (value - from_min) / (from_max - from_min)
        return to_min + normalized_value * (to_max - to_min)
        
    def process_final_frame(self, frame_buffer):
        """处理帧，并完整解析所有通道数据"""
        if len(frame_buffer) != NEW_FRAME_TOTAL_BYTES:
            return False, None

        try:
            # --- 1. 解析 O2(CH1) 和 O1(CH2) (不变) ---
            v_o2_ch1 = 0.0
            v_o1_ch2 = 0.0
            
            p1 = (frame_buffer[0] << 8) | frame_buffer[1]
            if (p1 >> 12) != 1: raise ValueError("CH1 校验失败")
            v_o2_ch1 = ((p1 & 0x0FFF) / 4095.0) * V_REF

            p2 = (frame_buffer[2] << 8) | frame_buffer[3]
            if (p2 >> 12) != 2: raise ValueError("CH2 校验失败")
            v_o1_ch2 = ((p2 & 0x0FFF) / 4095.0) * V_REF

            pressure_o1 = self.linear_map(v_o1_ch2, 1.5, 3.0, 100, 1000)
            temperature_o2 = self.linear_map(v_o2_ch1, 1.5, 3.0, -30, 200)

            # --- 2. [核心修改] 解析 CH3 (新格式) ---
            ch3_packet = frame_buffer[4:10]
            if ch3_packet[0] != SOF or ch3_packet[5] != EOF:
                raise ValueError("CH3 数据包帧头/帧尾错误")
            
            # 解析压力 (无符号16位整数)
            pressure_ch3_raw = (ch3_packet[1] << 8) | ch3_packet[2]
            pressure_ch3 = float(pressure_ch3_raw) # 单位 KPa
            
            # 解析温度 (有符号16位整数)
            temp_ch3_raw = (ch3_packet[3] << 8) | ch3_packet[4]
            # 使用struct库来处理有符号数(补码)，'>h'表示大端序的有符号短整型(16-bit)
            signed_temp_scaled = struct.unpack('>h', ch3_packet[3:5])[0]
            temperature_ch3 = signed_temp_scaled / 10.0 # 单位 ℃

            # --- 3. 校验 CH6,7,8 (不变) ---
            for idx, ch_num in enumerate([6, 7, 8]):
                offset = 10 + idx * 2
                p = (frame_buffer[offset] << 8) | frame_buffer[offset+1]
                if (p >> 12) != ch_num: raise ValueError(f"CH{ch_num} 校验失败")

            # --- [核心修改] 打包更完整的字典 ---
            final_data = {
                'o1_voltage': v_o1_ch2,
                'o1_pressure': pressure_o1,
                'o2_voltage': v_o2_ch1,
                'o2_temperature': temperature_o2,
                'ch3_pressure': pressure_ch3,
                'ch3_temperature': temperature_ch3
            }
            return True, final_data

        except (IndexError, ValueError, struct.error) as e:
            self.debug_message.emit(f"[协议错误] {e}")
            return False, None

    # --- run() 循环完全不变 ---
    def run(self):
        # (run函数无需任何修改)
        # ...
        try:
            self.serial_port.port = self.port_name
            self.serial_port.baudrate = 115200
            self.serial_port.timeout = 0.1
            if not self.serial_port.is_open:
                self.serial_port.open()
            self.debug_message.emit(f"串口 {self.port_name} 已打开，波特率 115200。")
        except serial.SerialException as e:
            self.debug_message.emit(f"[错误] 打开串口失败: {e}")
            self.running = False
            return

        frame_buffer = bytearray()
        while self.running:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(self.serial_port.in_waiting)
                frame_buffer.extend(data)
                while True:
                    if self._state == "HUNTING":
                        if len(frame_buffer) < 2: break
                        if (frame_buffer[0] >> 4) == 1:
                            if len(frame_buffer) >= NEW_FRAME_TOTAL_BYTES:
                                success, result_data = self.process_final_frame(frame_buffer[:NEW_FRAME_TOTAL_BYTES])
                                if success:
                                    self._state = "SYNCED"
                                    self.debug_message.emit("[状态] 帧同步成功，进入同步模式。")
                                    self.data_updated.emit(result_data)
                                    self.debug_message.emit(f"[接收成功] Frame: {' '.join(f'{b:02X}' for b in frame_buffer[:NEW_FRAME_TOTAL_BYTES])}")
                                    frame_buffer = frame_buffer[NEW_FRAME_TOTAL_BYTES:]
                                else: frame_buffer.pop(0)
                            else: break
                        else: frame_buffer.pop(0)
                    elif self._state == "SYNCED":
                        if len(frame_buffer) < NEW_FRAME_TOTAL_BYTES: break
                        success, result_data = self.process_final_frame(frame_buffer[:NEW_FRAME_TOTAL_BYTES])
                        if success:
                            self.data_updated.emit(result_data)
                            self.debug_message.emit(f"[接收成功] Frame: {' '.join(f'{b:02X}' for b in frame_buffer[:NEW_FRAME_TOTAL_BYTES])}")
                            frame_buffer = frame_buffer[NEW_FRAME_TOTAL_BYTES:]
                        else:
                            self._state = "HUNTING"
                            self.debug_message.emit("[状态] 同步丢失！回到狩猎模式...")
                            frame_buffer.pop(0)
            else:
                time.sleep(0.01)

        if self.serial_port.is_open:
            self.serial_port.close()
            self.debug_message.emit(f"串口 {self.port_name} 已关闭。")