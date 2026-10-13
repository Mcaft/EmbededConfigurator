# -*- coding: utf-8 -*-
"""WiFi 客户端配置页。"""
from PyQt5 import QtCore, QtWidgets


class WiFiTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._networks = []
        self._saved_conns = []
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QGridLayout()
        form.addWidget(QtWidgets.QLabel("SSID："), 0, 0)
        self.ssid_edit = QtWidgets.QLineEdit()
        form.addWidget(self.ssid_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("密码："), 1, 0)
        self.pwd_edit = QtWidgets.QLineEdit()
        self.pwd_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.show_pwd = QtWidgets.QCheckBox("显示")
        self.show_pwd.toggled.connect(self._toggle_pwd)
        pwd_row = QtWidgets.QHBoxLayout()
        pwd_row.addWidget(self.pwd_edit)
        pwd_row.addWidget(self.show_pwd)
        form.addLayout(pwd_row, 1, 1)
        layout.addLayout(form)

        scan_row = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton("扫描可用 WiFi")
        self.scan_status = QtWidgets.QLabel("")
        scan_row.addWidget(self.scan_btn)
        scan_row.addWidget(self.scan_status)
        scan_row.addStretch(1)
        layout.addLayout(scan_row)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["SSID", "信号强度", "加密方式"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

        # 已保存的 WiFi 连接（忘记网络）
        saved_row = QtWidgets.QHBoxLayout()
        saved_row.addWidget(QtWidgets.QLabel("已保存的 WiFi 连接："))
        self.saved_combo = QtWidgets.QComboBox()
        self.saved_combo.setMinimumWidth(220)
        self.saved_refresh_btn = QtWidgets.QPushButton("刷新")
        self.forget_btn = QtWidgets.QPushButton("忘记")
        saved_row.addWidget(self.saved_combo)
        saved_row.addWidget(self.saved_refresh_btn)
        saved_row.addWidget(self.forget_btn)
        saved_row.addStretch(1)
        layout.addLayout(saved_row)

        conn_row = QtWidgets.QHBoxLayout()
        self.connect_btn = QtWidgets.QPushButton("连接")
        conn_row.addWidget(self.connect_btn)
        conn_row.addStretch(1)
        layout.addLayout(conn_row)

        self.result_label = QtWidgets.QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.result_label)

        self.scan_btn.clicked.connect(self._on_scan)
        self.connect_btn.clicked.connect(self._on_connect)
        self.saved_refresh_btn.clicked.connect(self.refresh_saved)
        self.forget_btn.clicked.connect(self._on_forget)

        self.ssid_edit.setText(self.main.store.get("last_wifi_ssid", ""))
        self.pwd_edit.setText(self.main.store.get("last_wifi_password", ""))

    def _toggle_pwd(self, checked):
        self.pwd_edit.setEchoMode(
            QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password)

    # ---------------- 扫描 / 连接 ----------------
    def _on_scan(self):
        if not self.main.ensure_connected():
            return
        self.scan_btn.setEnabled(False)
        self.scan_status.setText("扫描中…")
        self.main.run_async(self.main.orin.scan_wifi, self._on_scan_done, self._on_scan_error)

    def _on_scan_done(self, networks):
        self.scan_btn.setEnabled(True)
        self.scan_status.setText(f"发现 {len(networks)} 个网络")
        self._networks = networks
        self.table.setRowCount(0)
        for n in networks:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(n["ssid"]))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{n['signal']}%"))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(n["security"]))
        self.main.logger.info(f"WiFi 扫描完成，共 {len(networks)} 个网络")

    def _on_scan_error(self, msg):
        self.scan_btn.setEnabled(True)
        self.scan_status.setText("扫描失败")
        self.main.show_error("WiFi 扫描失败", msg)

    def _on_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self._networks):
            self.ssid_edit.setText(self._networks[row]["ssid"])
            self.pwd_edit.setFocus()

    def _on_connect(self):
        ssid = self.ssid_edit.text().strip()
        password = self.pwd_edit.text()
        if not ssid:
            self.main.show_error("WiFi 连接", "请填写 SSID。")
            return
        if not self.main.ensure_connected():
            return
        self.connect_btn.setEnabled(False)
        self.result_label.setText("正在连接…")
        self.main.run_async(self.main.orin.connect_wifi,
                            self._on_connect_done, self._on_connect_error,
                            ssid, password)

    def _on_connect_done(self, result):
        self.connect_btn.setEnabled(True)
        ip = result.get("ip", "")
        self.result_label.setText(f"连接成功！WiFi IP：{ip}")
        self.main.store.set("last_wifi_ssid", self.ssid_edit.text().strip())
        self.main.store.set("last_wifi_password", self.pwd_edit.text())
        self.main.logger.info(f"WiFi 连接成功，IP={ip}")
        self.refresh_saved()
        self.main.request_status_refresh()

    def _on_connect_error(self, msg):
        self.connect_btn.setEnabled(True)
        self.result_label.setText("")
        self.main.show_error("WiFi 连接失败", msg)

    # ---------------- 已保存连接 / 忘记 ----------------
    def refresh_saved(self):
        if not self.main.ensure_connected():
            return
        self.saved_refresh_btn.setEnabled(False)
        self.main.run_async(self.main.orin.get_saved_wifi_connections,
                            self._on_saved_loaded, self._on_saved_error)

    def _on_saved_loaded(self, conns):
        self.saved_refresh_btn.setEnabled(True)
        self._saved_conns = conns
        self.saved_combo.clear()
        for c in conns:
            label = c["name"] + (f"  ({c['device']})" if c["device"] else "")
            self.saved_combo.addItem(label, c["name"])

    def _on_saved_error(self, msg):
        self.saved_refresh_btn.setEnabled(True)
        self.main.show_error("获取已保存 WiFi 失败", msg)

    def _on_forget(self):
        idx = self.saved_combo.currentIndex()
        if idx < 0 or idx >= len(self._saved_conns):
            self.main.show_error("忘记 WiFi", "请先刷新并选择要忘记的 WiFi 连接。")
            return
        name = self._saved_conns[idx]["name"]
        if not self.main.ensure_connected():
            return
        ret = QtWidgets.QMessageBox.question(
            self, "忘记 WiFi",
            f"确定要忘记（删除）WiFi 连接 “{name}” 吗？\n忘记后需重新输入密码才能连接。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if ret != QtWidgets.QMessageBox.Yes:
            return
        self.forget_btn.setEnabled(False)
        self.main.run_async(self.main.orin.forget_wifi,
                            self._on_forget_done, self._on_forget_error, name)

    def _on_forget_done(self, _):
        self.forget_btn.setEnabled(True)
        self.main.logger.info("已忘记 WiFi 连接")
        self.main.show_info("忘记 WiFi", "已成功忘记该 WiFi 连接。")
        self.refresh_saved()
        self.main.request_status_refresh()

    def _on_forget_error(self, msg):
        self.forget_btn.setEnabled(True)
        self.main.show_error("忘记 WiFi 失败", msg)
