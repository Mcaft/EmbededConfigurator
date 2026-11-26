# -*- coding: utf-8 -*-
"""Orin NX 地面站配置工具入口。"""
import os
import sys

from PyQt5 import QtGui, QtWidgets

from core.config import resource_path
from ui.main_window import MainWindow


def _load_stylesheet():
    path = resource_path(os.path.join("ui", "style.qss"))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _load_icon():
    # 优先用 .ico（Windows 任务栏/窗口图标），回退到 .svg
    for name in ("icon.ico", "icon.svg"):
        path = resource_path(name)
        if os.path.exists(path):
            return QtGui.QIcon(path)
    return QtGui.QIcon()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(_load_stylesheet())
    icon = _load_icon()
    app.setWindowIcon(icon)
    win = MainWindow()
    win.setWindowIcon(icon)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
