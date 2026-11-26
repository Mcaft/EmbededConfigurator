# -*- coding: utf-8 -*-
"""Orin NX 地面站配置工具入口。"""
import os
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

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


def _enable_high_dpi():
    """开启高 DPI 缩放，必须在创建 QApplication 之前调用。"""
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    # 允许 125% / 150% 等非整数缩放，避免被取整后界面偏小（Qt 5.14+）
    policy = getattr(QtCore.Qt, "HighDpiScaleFactorRoundingPolicy", None)
    if policy is not None:
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            policy.PassThrough)


def main():
    _enable_high_dpi()
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
