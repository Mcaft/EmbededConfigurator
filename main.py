# -*- coding: utf-8 -*-
"""Orin NX 地面站配置工具入口。"""
import os
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

from core import scaling
from core.config import resource_path
from core.store import Store
from ui.main_window import MainWindow


def _load_stylesheet():
    path = resource_path(os.path.join("ui", "style.qss"))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _load_icon():
    # Windows 优先 .ico（任务栏/窗口图标），Linux 优先 .png / .svg
    if sys.platform.startswith("win"):
        names = ("icon.ico", "icon.png", "icon.svg")
    else:
        names = ("icon.png", "icon.svg", "icon.ico")
    for name in names:
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

    # 界面缩放：读取上次保存的缩放比例（Ctrl+= / Ctrl+- / Ctrl+0 调整）
    scaling.set_base_stylesheet(_load_stylesheet())
    scaling.set_scale(Store().get("ui_scale", scaling.DEFAULT_SCALE))
    app.setStyleSheet(scaling.scale_stylesheet())
    icon = _load_icon()
    app.setWindowIcon(icon)
    win = MainWindow()
    win.setWindowIcon(icon)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
