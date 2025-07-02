# 文件名: main.py
import sys
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    from PyQt5.QtCore import Qt
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)  # 必须在创建 QApplication 之前

    from main_window import MainWindow
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())