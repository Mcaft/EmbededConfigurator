# -*- coding: utf-8 -*-
"""Orin NX 地面站配置工具入口。"""
import os
import sys

from PyQt5 import QtWidgets

from core.config import app_dir
from ui.main_window import MainWindow


def _load_stylesheet():
    path = os.path.join(app_dir(), "ui", "style.qss")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(_load_stylesheet())
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
