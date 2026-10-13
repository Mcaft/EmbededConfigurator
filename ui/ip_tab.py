# -*- coding: utf-8 -*-
"""Orin 自身 IP 配置页。"""
from PyQt5 import QtCore, QtWidgets

from core.orin import mask_to_prefix


class IPTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._connections = []
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        sel_box = QtWidgets.QGroupBox("选择要配置的连接（接口）")
        sel_lay = QtWidgets.QHBoxLayout(sel_box)
        self.conn_combo = QtWidgets.QComboBox()
        self.conn_combo.setMinimumWidth(280)
        self.refresh_btn = QtWidgets.QPushButton("刷新接口列表")
        sel_lay.addWidget(self.conn_combo)
        sel_lay.addWidget(self.refresh_btn)
        sel_lay.addStretch(1)
        layout.addWidget(sel_box)

        mode_box = QtWidgets.QGroupBox("IP 模式")
        mode_lay = QtWidgets.QHBoxLayout(mode_box)
        self.static_radio = QtWidgets.QRadioButton("静态 IP")
        self.dhcp_radio = QtWidgets.QRadioButton("DHCP")
        self.static_radio.setChecked(True)
        mode_lay.addWidget(self.static_radio)
        mode_lay.addWidget(self.dhcp_radio)
        mode_lay.addStretch(1)
        layout.addWidget(mode_box)

        self.static_group = QtWidgets.QGroupBox("静态 IP 参数")
        grid = QtWidgets.QGridLayout(self.static_group)
        grid.addWidget(QtWidgets.QLabel("IP 地址："), 0, 0)
        self.ip_edit = QtWidgets.QLineEdit("192.168.55.2")
        grid.addWidget(self.ip_edit, 0, 1)
        grid.addWidget(QtWidgets.QLabel("子网掩码："), 1, 0)
        self.mask_combo = QtWidgets.QComboBox()
        self.mask_combo.addItems(["255.255.255.0", "255.255.0.0", "255.0.0.0"])
        grid.addWidget(self.mask_combo, 1, 1)
        grid.addWidget(QtWidgets.QLabel("网关："), 2, 0)
        self.gateway_edit = QtWidgets.QLineEdit()
        grid.addWidget(self.gateway_edit, 2, 1)
        grid.addWidget(QtWidgets.QLabel("DNS："), 3, 0)
        self.dns_edit = QtWidgets.QLineEdit()
        grid.addWidget(self.dns_edit, 3, 1)
        layout.addWidget(self.static_group)

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

        self.refresh_btn.clicked.connect(self.refresh)
        self.apply_btn.clicked.connect(self._on_apply)
        self.static_radio.toggled.connect(self.static_group.setEnabled)

    def refresh(self):
        if not self.main.ensure_connected():
            return
        self.refresh_btn.setEnabled(False)
        self.main.run_async(self._load_connections, self._on_refresh_done, self._on_refresh_error)

    def _load_connections(self):
        conns = self.main.orin.get_connections()
        devices = {d["device"]: d for d in self.main.orin.get_interfaces()}
        result = []
        for c in conns:
            dev = devices.get(c["device"], {})
            result.append({
                "name": c["name"], "type": c["type"], "device": c["device"],
                "state": dev.get("state", ""),
            })
        return result

    def _on_refresh_done(self, conns):
        self.refresh_btn.setEnabled(True)
        self._connections = conns
        self.conn_combo.clear()
        for c in conns:
            label = f"{c['name']}  [{c['type']}]  ({c['device'] or '无设备'})"
            self.conn_combo.addItem(label, c["name"])
        self.main.logger.info(f"接口列表刷新完成，共 {len(conns)} 个连接")

    def _on_refresh_error(self, msg):
        self.refresh_btn.setEnabled(True)
        self.main.show_error("刷新接口失败", msg)

    def _on_apply(self):
        idx = self.conn_combo.currentIndex()
        if idx < 0 or idx >= len(self._connections):
            self.main.show_error("IP 配置", "请先刷新并选择要配置的连接。")
            return
        conn = self._connections[idx]
        if not self.main.ensure_connected():
            return

        if self.dhcp_radio.isChecked():
            self.apply_btn.setEnabled(False)
            self.result_label.setText("正在切换为 DHCP…")
            self.main.run_async(self.main.orin.set_dhcp,
                                self._on_apply_done, self._on_apply_error, conn["name"])
            return

        ip = self.ip_edit.text().strip()
        mask = self.mask_combo.currentText()
        gateway = self.gateway_edit.text().strip()
        dns = self.dns_edit.text().strip()
        if not ip:
            self.main.show_error("IP 配置", "请填写 IP 地址。")
            return
        prefix = mask_to_prefix(mask)
        if prefix is None:
            self.main.show_error("IP 配置", "子网掩码无效。")
            return
        self.apply_btn.setEnabled(False)
        self.result_label.setText("正在应用静态 IP…")
        self.main.run_async(self.main.orin.set_static_ip,
                            self._on_apply_done, self._on_apply_error,
                            conn["name"], ip, prefix, gateway, dns)

    def _on_apply_done(self, ips):
        self.apply_btn.setEnabled(True)
        if ips:
            text = "配置成功！\n当前接口地址：\n" + "\n".join(
                f"  {i['interface']}: {i['ip']}/{i['prefix']}" for i in ips)
        else:
            text = "配置成功！"
        self.result_label.setText(text)
        self.main.logger.info("IP 配置已应用")
        self.main.request_status_refresh()

    def _on_apply_error(self, msg):
        self.apply_btn.setEnabled(True)
        self.result_label.setText("")
        self.main.show_error("IP 配置失败", msg)
