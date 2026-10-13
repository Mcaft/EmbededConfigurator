# -*- coding: utf-8 -*-
"""热点（AP）配置页。"""
from PyQt5 import QtCore, QtWidgets

from core.config import HOTSPOT_DEFAULT_IP


class HotspotTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        box = QtWidgets.QGroupBox("热点（AP）配置")
        grid = QtWidgets.QGridLayout(box)
        self.enable_check = QtWidgets.QCheckBox("启用热点")
        grid.addWidget(self.enable_check, 0, 0, 1, 2)
        grid.addWidget(QtWidgets.QLabel("热点 SSID："), 1, 0)
        self.ssid_edit = QtWidgets.QLineEdit()
        grid.addWidget(self.ssid_edit, 1, 1)
        grid.addWidget(QtWidgets.QLabel("热点密码："), 2, 0)
        self.pwd_edit = QtWidgets.QLineEdit()
        self.pwd_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.show_pwd = QtWidgets.QCheckBox("显示")
        self.show_pwd.toggled.connect(self._toggle_pwd)
        pwd_row = QtWidgets.QHBoxLayout()
        pwd_row.addWidget(self.pwd_edit)
        pwd_row.addWidget(self.show_pwd)
        grid.addLayout(pwd_row, 2, 1)
        self.autoconnect_check = QtWidgets.QCheckBox("开机自启动")
        grid.addWidget(self.autoconnect_check, 3, 0, 1, 2)
        grid.addWidget(QtWidgets.QLabel(f"热点默认网关：{HOTSPOT_DEFAULT_IP}"), 4, 0, 1, 2)
        layout.addWidget(box)

        self.warn_label = QtWidgets.QLabel(
            "提示：WiFi 网卡同一时刻通常只能作为客户端（连接 WiFi）或热点（AP）二选一。"
            "开启热点前请先断开 WiFi 客户端连接。")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet("color: #b58900;")
        layout.addWidget(self.warn_label)

        apply_row = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用")
        apply_row.addWidget(self.apply_btn)
        apply_row.addStretch(1)
        layout.addLayout(apply_row)

        self.result_label = QtWidgets.QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.result_label)
        layout.addStretch(1)

        self.apply_btn.clicked.connect(self._on_apply)

        self.ssid_edit.setText(self.main.store.get("last_hotspot_ssid", "HC-Hotspot"))
        self.pwd_edit.setText(self.main.store.get("last_hotspot_password", ""))
        self.autoconnect_check.setChecked(bool(self.main.store.get("last_hotspot_autoconnect", True)))

    def _toggle_pwd(self, checked):
        self.pwd_edit.setEchoMode(
            QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password)

    def _on_apply(self):
        ssid = self.ssid_edit.text().strip()
        password = self.pwd_edit.text()
        if not ssid:
            self.main.show_error("热点配置", "请填写热点 SSID。")
            return
        if len(password) < 8:
            self.main.show_error("热点配置", "热点密码至少需要 8 位。")
            return
        if not self.main.ensure_connected():
            return
        self.apply_btn.setEnabled(False)
        self.result_label.setText("正在应用热点配置…")
        self.main.run_async(
            self.main.orin.configure_hotspot, self._on_apply_done, self._on_apply_error,
            self.enable_check.isChecked(), ssid, password, self.autoconnect_check.isChecked())

    def _on_apply_done(self, _):
        self.apply_btn.setEnabled(True)
        self.result_label.setText("热点配置成功。")
        self.main.store.set("last_hotspot_ssid", self.ssid_edit.text().strip())
        self.main.store.set("last_hotspot_password", self.pwd_edit.text())
        self.main.store.set("last_hotspot_autoconnect", self.autoconnect_check.isChecked())
        self.main.logger.info("热点配置已应用")
        self.main.request_status_refresh()

    def _on_apply_error(self, msg):
        self.apply_btn.setEnabled(True)
        self.result_label.setText("")
        self.main.show_error("热点配置失败", msg)
