# -*- coding: utf-8 -*-
"""顶部连接状态栏。"""
from PyQt5 import QtCore, QtWidgets

from core.config import MODE_RNDIS


class ConnectionBar(QtWidgets.QWidget):
    detect_requested = QtCore.pyqtSignal()
    host_config_requested = QtCore.pyqtSignal()
    connect_requested = QtCore.pyqtSignal()
    disconnect_requested = QtCore.pyqtSignal()
    settings_requested = QtCore.pyqtSignal()
    board_changed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        # 板卡
        board_box = QtWidgets.QGroupBox("板卡")
        board_lay = QtWidgets.QHBoxLayout(board_box)
        self.board_combo = QtWidgets.QComboBox()
        self.board_combo.setMinimumWidth(140)
        self.mode_label = QtWidgets.QLabel("连接方式：-")
        board_lay.addWidget(self.board_combo)
        board_lay.addWidget(self.mode_label)

        # 本机 RNDIS（仅 RNDIS 模式显示）
        self.rndis_box = QtWidgets.QGroupBox("本机（RNDIS）")
        rndis_lay = QtWidgets.QHBoxLayout(self.rndis_box)
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
        self.orin_ip_label = QtWidgets.QLabel("Orin IP：-")
        self.connect_btn = QtWidgets.QPushButton("连接")
        orin_lay.addWidget(self.ssh_label)
        orin_lay.addWidget(self.orin_ip_label)
        orin_lay.addWidget(self.connect_btn)

        self.settings_btn = QtWidgets.QPushButton("设置")

        layout.addWidget(board_box)
        layout.addWidget(self.rndis_box)
        layout.addWidget(orin_box)
        layout.addWidget(self.settings_btn)
        layout.addStretch(1)

        self.board_combo.currentIndexChanged.connect(self._on_combo_changed)
        self.detect_btn.clicked.connect(self.detect_requested)
        self.host_config_btn.clicked.connect(self.host_config_requested)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.settings_btn.clicked.connect(self.settings_requested)

        self._state = "disconnected"

    def _on_combo_changed(self, idx):
        name = self.board_combo.itemData(idx)
        if name:
            self.board_changed.emit(name)

    def _on_connect_clicked(self):
        if self._state == "connected":
            self.disconnect_requested.emit()
        else:
            self.connect_requested.emit()

    def set_boards(self, names, active_name):
        self.board_combo.blockSignals(True)
        self.board_combo.clear()
        for n in names:
            self.board_combo.addItem(n, n)
        idx = self.board_combo.findData(active_name)
        self.board_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.board_combo.blockSignals(False)

    def apply_board(self, board):
        is_rndis = board.get("mode") == MODE_RNDIS
        self.mode_label.setText("连接方式：USB RNDIS" if is_rndis else "连接方式：局域网")
        self.rndis_box.setVisible(is_rndis)
        self.set_orin_ip(board.get("ssh_host") or "未填写")

    def set_rndis_status(self, text):
        self.rndis_label.setText(f"网卡：{text}")

    def set_host_ip(self, text):
        self.host_ip_label.setText(f"本机IP：{text}")

    def set_orin_ip(self, text):
        self.orin_ip_label.setText(f"Orin IP：{text}")

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
