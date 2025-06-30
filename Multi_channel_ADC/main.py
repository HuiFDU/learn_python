# 文件名: main.py
import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 启用高清屏适配
    try:
        from PyQt5.QtCore import Qt
        app.setAttribute(Qt.AA_EnableHighDpiScaling)
    except AttributeError:
        pass
        
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())