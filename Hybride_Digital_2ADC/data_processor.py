# 文件名: data_processor.py (Rev 2.3 - 物理量计算)
# Hui & Rongrong & Gemini 合作开发版本
#
# Rev 2.3 修改:
# - 在解析电压后，直接计算出O1(压力)和O2(温度)的物理量。
# - data_updated 信号现在传递一个包含物理量字典。
# - 旧的voltages列表不再向主线程传递。


import serial
import serial.tools.list_ports
import time
from PyQt5.QtCore import QThread, pyqtSignal

# --- 常量定义 (保持不变) ---
NEW_FRAME_TOTAL_BYTES = 16
V_REF = 3.0
SOF = 0xAF
EOF = 0xFA

class DataProcessor(QThread):
    # --- [核心修改] 修改信号，使其传递一个字典，更具可读性 ---
    data_updated = pyqtSignal(dict)
    debug_message = pyqtSignal(str)

    # __init__, start_processing, stop_processing 保持不变...
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


    # --- [核心修改] 线性转换函数 ---
    def linear_map(self, value, from_min, from_max, to_min, to_max):
        """通用的线性映射函数"""
        # 防止除以零
        if (from_max - from_min) == 0:
            return to_min
        # 计算比例
        normalized_value = (value - from_min) / (from_max - from_min)
        # 映射到新范围
        return to_min + normalized_value * (to_max - to_min)

    # --- [核心修改] process_final_frame 返回更丰富的数据 ---
    def process_final_frame(self, frame_buffer):
        """处理帧并计算物理量"""
        if len(frame_buffer) != NEW_FRAME_TOTAL_BYTES:
            return False, None

        try:
            # --- 1. 解析 CH1 (O2) 和 CH2 (O1) 的电压 ---
            v_o2_ch1 = 0.0
            v_o1_ch2 = 0.0
            
            # CH1 -> O2
            h1, l1 = frame_buffer[0], frame_buffer[1]
            p1 = (h1 << 8) | l1
            ch1 = p1 >> 12
            adc1 = p1 & 0x0FFF
            if ch1 != 1: raise ValueError("CH1 校验失败")
            v_o2_ch1 = (adc1 / 4095.0) * V_REF

            # CH2 -> O1
            h2, l2 = frame_buffer[2], frame_buffer[3]
            p2 = (h2 << 8) | l2
            ch2 = p2 >> 12
            adc2 = p2 & 0x0FFF
            if ch2 != 2: raise ValueError("CH2 校验失败")
            v_o1_ch2 = (adc2 / 4095.0) * V_REF

            # --- 2. [核心修改] 进行物理量计算 ---
            # O1 (压力, KPa)
            pressure = self.linear_map(v_o1_ch2, 1.5, 3.0, 100, 1000)
            
            # O2 (温度, ℃)
            temperature = self.linear_map(v_o2_ch1, 1.5, 3.0, -30, 200)

            # --- 3. 解析但不处理其他通道（为了协议完整性） ---
            # ... (这部分解析逻辑可以保留，以确保帧校验的完整性) ...
            ch3_packet = frame_buffer[4:10]
            if ch3_packet[0] != SOF or ch3_packet[5] != EOF:
                raise ValueError("CH3 数据包帧头/帧尾错误")
            
            for idx, ch_num in enumerate([6, 7, 8]):
                offset = 10 + idx * 2
                h, l = frame_buffer[offset], frame_buffer[offset+1]
                p = (h << 8) | l
                ch = p >> 12
                if ch != ch_num: raise ValueError(f"CH{ch_num} 校验失败")
            
            # --- [核心修改] 将所有需要的数据打包成字典 ---
            final_data = {
                'o1_voltage': v_o1_ch2,
                'o1_pressure': pressure,
                'o2_voltage': v_o2_ch1,
                'o2_temperature': temperature
            }
            return True, final_data

        except (IndexError, ValueError) as e:
            self.debug_message.emit(f"[协议错误] {e}")
            return False, None

    # --- run() 循环修改以适应新的返回数据类型 ---
    def run(self):
        # ... (串口打开和主循环逻辑保持不变, 只需修改成功处理后的信号发射) ...
        # (此处省略大部分 run 代码, 只展示修改点)
        while self.running:
            # ...
                # 在 HUNTING 和 SYNCED 状态中，当解析成功时:
                # success, result_data = self.process_final_frame(...)
                # if success:
                #     self.data_updated.emit(result_data)
            # ...
            # 详细代码如下
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