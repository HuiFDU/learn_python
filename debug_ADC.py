#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12位ADC电压转换器
参考电压: 3.0V
分辨率: 12位 (0-4095)
"""

def voltage_to_adc_hex(voltage, vref=2.998, bits=12):
    """
    将输入电压转换为ADC的16进制值
    
    参数:
    voltage (float): 输入电压值 (V)
    vref (float): ADC参考电压 (V), 默认3.0V
    bits (int): ADC位数, 默认12位
    
    返回:
    str: 16进制ADC值
    """
    # 计算最大ADC值
    max_adc_value = (2 ** bits) - 1
    
    # 检查输入电压范围
    if voltage < 0:
        voltage = 0
        print(f"警告: 输入电压小于0V，已调整为0V")
    elif voltage > vref:
        voltage = vref
        print(f"警告: 输入电压超过参考电压{vref}V，已调整为{vref}V")
    
    # 计算ADC值
    adc_value = int((voltage / vref) * max_adc_value)
    
    # 转换为16进制（去掉0x前缀，大写格式）
    hex_value = format(adc_value, '03X')  # 至少3位16进制
    
    return hex_value, adc_value

def main():
    """主程序 - 实时电压输入和ADC转换"""
    print("=" * 50)
    print("12位ADC电压转换器")
    print("参考电压: 3.0V")
    print("输入范围: 0V - 3.0V")
    print("输出: 16进制ADC值 (000-FFF)")
    print("=" * 50)
    print("输入 'q' 或 'quit' 退出程序")
    print()
    
    while True:
        try:
            # 获取用户输入
            user_input = input("请输入电压值 (V): ").strip()
            
            # 检查退出命令
            if user_input.lower() in ['q', 'quit', '退出']:
                print("程序已退出")
                break
            
            # 转换为浮点数
            voltage = float(user_input)
            
            # 进行ADC转换
            hex_value, adc_value = voltage_to_adc_hex(voltage)
            
            # 显示结果
            print(f"输入电压: {voltage:.3f}V")
            print(f"ADC十进制值: {adc_value}")
            print(f"ADC十六进制值: 0x{hex_value}")
            print(f"二进制值: {format(adc_value, '012b')}")
            print("-" * 30)
            
        except ValueError:
            print("错误: 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n程序被用户中断")
            break
        except Exception as e:
            print(f"发生错误: {e}")

def batch_convert(voltage_list):
    """批量转换电压列表"""
    print("\n批量转换结果:")
    print("电压(V)  | ADC十进制 | ADC十六进制")
    print("-" * 35)
    
    for voltage in voltage_list:
        hex_value, adc_value = voltage_to_adc_hex(voltage)
        print(f"{voltage:6.3f}  |   {adc_value:4d}    |    0x{hex_value}")

# 示例用法
if __name__ == "__main__":
    # 显示一些示例转换
    print("示例转换:")
    test_voltages = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    batch_convert(test_voltages)
    print()
    
    # 开始实时转换程序
    main()