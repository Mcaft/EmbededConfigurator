# -*- coding: utf-8 -*-
"""顶部连接状态栏。"""
from PyQt5 import QtCore, QtWidgets

from core.config import ORIN_IP


class ConnectionBar(QtWidgets.QWidget):
    detect_requested = QtCore.pyqtSignal()
    host_config_requested = QtCore.pyqtSignal()
    connect_requested = QtCore.pyqtSignal()
    disconnect_requested = QtCore.pyqtSignal()
    settings_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        # 本机 RNDIS
        rndis_box = QtWidgets.QGroupBox("本机（RNDIS）")
        rndis_lay = QtWidgets.QHBoxLayout(rndis_box)
        self.rndis_label = QtWidgets.QLabel("网卡：未检测")
        self.host_ip_label = QtWidgets.QLabel("本机IP：-")
        self.detect_btn = QtWidgets.QPushButton("检测 RNDIS")
        self.host_config_btn = QtWidgets.QPushButton("配置本机 IP")
        rndis_lay.addWidget(self.rndis_label)
        rndis_lay.addWidget(self.host_ip_label)
        rndis_lay.addWidget(self.detect_btn)
        rndis_lay.addWidget(self.host_config_btn)

        # Orin 连接
        orin_box = QtWidgets.QGroupBox("Orin NX")
        orin_lay = QtWidgets.QHBoxLayout(orin_box)
        self.ssh_label = QtWidgets.QLabel("SSH：未连接")
        self.orin_ip_label = QtWidgets.QLabel(f"Orin IP：{ORIN_IP}")
        self.connect_btn = QtWidgets.QPushButton("连接")
        orin_lay.addWidget(self.ssh_label)
        orin_lay.addWidget(self.orin_ip_label)
        orin_lay.addWidget(self.connect_btn)

        self.settings_btn = QtWidgets.QPushButton("设置")

        layout.addWidget(rndis_box)
        layout.addWidget(orin_box)
        layout.addWidget(self.settings_btn)
        layout.addStretch(1)

        self.detect_btn.clicked.connect(self.detect_requested)
        self.host_config_btn.clicked.connect(self.host_config_requested)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.settings_btn.clicked.connect(self.settings_requested)

        self._state = "disconnected"

    def _on_connect_clicked(self):
        if self._state == "connected":
            self.disconnect_requested.emit()
        else:
            self.connect_requested.emit()

    def set_rndis_status(self, text):
        self.rndis_label.setText(f"网卡：{text}")

    def set_host_ip(self, text):
        self.host_ip_label.setText(f"本机IP：{text}")

    def set_ssh_state(self, state, text=None):
        """state: disconnected / connecting / connected"""
        self._state = state
        if state == "connecting":
            self.connect_btn.setText("连接中…")
            self.connect_btn.setEnabled(False)
            self.ssh_label.setText("SSH：连接中…")
        elif state == "connected":
            self.connect_btn.setText("断开")
            self.connect_btn.setEnabled(True)
            self.ssh_label.setText(f"SSH：已连接 {text or ''}".strip())
        else:
            self.connect_btn.setText("连接")
            self.connect_btn.setEnabled(True)
            self.ssh_label.setText(f"SSH：未连接 {text or ''}".strip())
