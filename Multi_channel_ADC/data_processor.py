# 文件名: data_processor.py

import serial
import serial.tools.list_ports
import time
from PyQt5.QtCore import QThread, pyqtSignal

# 定义协议常量
NUM_CHANNELS = 8
BYTES_PER_FRAME = NUM_CHANNELS * 2 # 8个通道，每个通道2字节
V_REF = 3.0  # 参考电压

class DataProcessor(QThread):
    # 定义信号：一个用于传递8个电压值的列表，另一个用于传递调试信息
    data_updated = pyqtSignal(list)
    debug_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = serial.Serial()
        self.port_name = ""
        self.running = False
        self._state = "HUNTING" # 初始状态为“狩猎”模式

    def start_processing(self, port_name):
        """启动数据处理线程"""
        if self.isRunning():
            return
        self.port_name = port_name
        self.running = True
        self._state = "HUNTING" # 每次启动都从狩猎模式开始
        self.start() # QThread的启动方法

    def stop_processing(self):
        """停止数据处理线程"""
        self.running = False
        self.wait() # 等待线程安全退出

    def process_frame(self, frame_buffer):
        """处理一个16字节的数据帧"""
        voltages = [0.0] * NUM_CHANNELS
        valid_frame = True
        
        for i in range(NUM_CHANNELS):
            # 从帧中提取高低字节
            high_byte = frame_buffer[i * 2]
            low_byte = frame_buffer[i * 2 + 1]

            # 组合成16位数据
            packed_data = (high_byte << 8) | low_byte

            # 解包出通道号和ADC值
            channel = packed_data >> 12
            adc_value = packed_data & 0x0FFF

            # --- 协议校验 ---
            expected_channel = i + 1
            if channel != expected_channel:
                self.debug_message.emit(
                    f"[协议错误] 在帧内位置 {i} 期望通道 {expected_channel}, 但得到 {channel}. "
                    f"原始字节: {high_byte:02X} {low_byte:02X}"
                )
                valid_frame = False
                break # 当前帧无效，跳出循环
            
            # 计算电压
            voltage = (adc_value / 4095.0) * V_REF
            voltages[i] = voltage
        
        if valid_frame:
            # 如果整帧都有效，则发出更新信号
            self.data_updated.emit(voltages)
            # 在debug窗口显示成功接收的原始数据
            self.debug_message.emit(f"[接收成功] Frame: {' '.join(f'{b:02X}' for b in frame_buffer)}")

        return valid_frame

    def run(self):
        """线程的主循环"""
        try:
            self.serial_port.port = self.port_name
            self.serial_port.baudrate = 115200
            self.serial_port.timeout = 0.1 # 设置一个短的超时，避免永久阻塞
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
                # 读取所有可用数据
                bytes_to_read = self.serial_port.in_waiting
                data = self.serial_port.read(bytes_to_read)
                
                # 将新数据添加到缓冲区
                frame_buffer.extend(data)

                # --- 状态机逻辑 ---
                while len(frame_buffer) >= 2: # 至少要有2个字节才能开始判断
                    if self._state == "HUNTING":
                        # 狩猎模式: 寻找通道1的包头
                        high_byte = frame_buffer[0]
                        
                        # 检查高字节的高4位是否是 0x1
                        if (high_byte >> 4) == 1:
                            if len(frame_buffer) >= BYTES_PER_FRAME:
                                # 缓冲区足够长，可以尝试验证一整帧
                                potential_frame = frame_buffer[:BYTES_PER_FRAME]
                                if self.process_frame(potential_frame):
                                    # 验证成功！进入同步模式
                                    self._state = "SYNCED"
                                    self.debug_message.emit("[状态] 帧同步成功，进入同步模式。")
                                    # 移除已处理的数据
                                    frame_buffer = frame_buffer[BYTES_PER_FRAME:]
                                else:
                                    # 验证失败，丢弃一个字节，继续狩猎
                                    frame_buffer.pop(0)
                            else:
                                # 缓冲区不够一帧，等待更多数据
                                break
                        else:
                            # 不是通道1的包头，丢弃一个字节
                            frame_buffer.pop(0)

                    elif self._state == "SYNCED":
                        # 同步模式: 按块处理数据
                        if len(frame_buffer) >= BYTES_PER_FRAME:
                            current_frame = frame_buffer[:BYTES_PER_FRAME]
                            if self.process_frame(current_frame):
                                # 成功处理，移除已处理的数据
                                frame_buffer = frame_buffer[BYTES_PER_FRAME:]
                            else:
                                # 同步丢失！回到狩猎模式
                                self._state = "HUNTING"
                                self.debug_message.emit("[状态] 同步丢失！回到狩猎模式...")
                                # 这里我们选择丢弃整个被认为是错误的帧，也可以只丢弃一个字节
                                frame_buffer = frame_buffer[BYTES_PER_FRAME:]
                        else:
                            # 缓冲区不够一帧，等待更多数据
                            break
            else:
                # 稍微等待一下，避免CPU空转
                time.sleep(0.01)

        if self.serial_port.is_open:
            self.serial_port.close()
            self.debug_message.emit(f"串口 {self.port_name} 已关闭。")