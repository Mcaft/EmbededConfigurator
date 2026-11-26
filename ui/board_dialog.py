# -*- coding: utf-8 -*-
"""板卡管理对话框：添加/删除/编辑板卡的连接配置。"""
from PyQt5 import QtWidgets

from core.config import MODE_LAN, MODE_RNDIS, ORIN_USERNAME


class BoardDialog(QtWidgets.QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self._boards = [dict(b) for b in store.get_boards()]  # 工作副本，取消则丢弃
        self._idx = 0
        active = store.get_active_board_name()
        for i, b in enumerate(self._boards):
            if b.get("name") == active:
                self._idx = i
                break

        self.setWindowTitle("板卡设置")
        self.resize(560, 380)
        self._build()
        self._refresh_list(select_index=self._idx)
        self._fill(self._boards[self._idx] if self._boards else None)

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)

        body = QtWidgets.QHBoxLayout()

        left = QtWidgets.QVBoxLayout()
        self.list = QtWidgets.QListWidget()
        self.list.setMinimumWidth(160)
        left.addWidget(self.list)
        btn_row = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("新增")
        self.del_btn = QtWidgets.QPushButton("删除")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.del_btn)
        left.addLayout(btn_row)
        body.addLayout(left)

        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        form.addRow("板卡名称：", self.name_edit)
        mode_row = QtWidgets.QHBoxLayout()
        self.mode_rndis = QtWidgets.QRadioButton("USB RNDIS")
        self.mode_lan = QtWidgets.QRadioButton("局域网")
        mode_row.addWidget(self.mode_rndis)
        mode_row.addWidget(self.mode_lan)
        mode_row.addStretch(1)
        form.addRow("连接方式：", mode_row)
        self.host_edit = QtWidgets.QLineEdit()
        form.addRow("SSH IP：", self.host_edit)
        self.port_spin = QtWidgets.QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        form.addRow("端口：", self.port_spin)
        self.user_edit = QtWidgets.QLineEdit()
        form.addRow("用户名：", self.user_edit)
        self.pwd_edit = QtWidgets.QLineEdit()
        self.pwd_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("密码：", self.pwd_edit)
        body.addLayout(form, 1)
        root.addLayout(body, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("保存当前")
        self.ok_btn = QtWidgets.QPushButton("设为当前并关闭")
        self.cancel_btn = QtWidgets.QPushButton("取消")
        bottom.addStretch(1)
        bottom.addWidget(self.save_btn)
        bottom.addWidget(self.ok_btn)
        bottom.addWidget(self.cancel_btn)
        root.addLayout(bottom)

        self.list.currentRowChanged.connect(self._on_select)
        self.add_btn.clicked.connect(self._on_add)
        self.del_btn.clicked.connect(self._on_delete)
        self.save_btn.clicked.connect(self._on_save_current)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    # ---------------- 数据 <-> 界面 ----------------
    def _fill(self, board):
        if board is None:
            return
        self.name_edit.setText(board.get("name", ""))
        if board.get("mode") == MODE_RNDIS:
            self.mode_rndis.setChecked(True)
        else:
            self.mode_lan.setChecked(True)
        self.host_edit.setText(board.get("ssh_host", ""))
        self.port_spin.setValue(int(board.get("ssh_port", 22) or 22))
        self.user_edit.setText(board.get("ssh_username", ""))
        self.pwd_edit.setText(board.get("ssh_password", ""))

    def _commit_current(self):
        if not 0 <= self._idx < len(self._boards):
            return
        b = self._boards[self._idx]
        b["name"] = self.name_edit.text().strip() or b["name"]
        b["mode"] = MODE_RNDIS if self.mode_rndis.isChecked() else MODE_LAN
        b["ssh_host"] = self.host_edit.text().strip()
        b["ssh_port"] = self.port_spin.value()
        b["ssh_username"] = self.user_edit.text().strip()
        b["ssh_password"] = self.pwd_edit.text()

    def _refresh_list(self, select_index=None):
        if select_index is None:
            select_index = self._idx
        self.list.blockSignals(True)
        self.list.clear()
        for b in self._boards:
            self.list.addItem(b["name"])
        if 0 <= select_index < len(self._boards):
            self.list.setCurrentRow(select_index)
        self.list.blockSignals(False)

    # ---------------- 槽 ----------------
    def _on_select(self, row):
        self._commit_current()
        self._refresh_list(select_index=row)
        if 0 <= row < len(self._boards):
            self._idx = row
            self._fill(self._boards[row])

    def _on_save_current(self):
        self._commit_current()
        self._refresh_list()

    def _on_add(self):
        self._commit_current()
        name = self._unique_name("新板卡")
        self._boards.append({
            "name": name, "mode": MODE_LAN, "ssh_host": "",
            "ssh_port": 22, "ssh_username": ORIN_USERNAME, "ssh_password": "",
        })
        self._idx = len(self._boards) - 1
        self._refresh_list(select_index=self._idx)
        self._fill(self._boards[self._idx])

    def _on_delete(self):
        if not 0 <= self._idx < len(self._boards):
            return
        if len(self._boards) <= 1:
            QtWidgets.QMessageBox.warning(self, "删除板卡", "至少保留一个板卡。")
            return
        name = self._boards[self._idx]["name"]
        ret = QtWidgets.QMessageBox.question(
            self, "删除板卡", f"确定删除板卡「{name}」吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if ret != QtWidgets.QMessageBox.Yes:
            return
        del self._boards[self._idx]
        self._idx = min(self._idx, len(self._boards) - 1)
        self._refresh_list(select_index=self._idx)
        self._fill(self._boards[self._idx])

    def _unique_name(self, base):
        names = {b["name"] for b in self._boards}
        if base not in names:
            return base
        i = 2
        while f"{base}{i}" in names:
            i += 1
        return f"{base}{i}"

    # ---------------- 确认 / 取消 ----------------
    def accept(self):
        self._commit_current()
        if not self._boards:
            QtWidgets.QMessageBox.warning(self, "板卡设置", "至少保留一个板卡。")
            return
        for b in self._boards:
            b["name"] = b["name"].strip()
            if not b["name"]:
                QtWidgets.QMessageBox.warning(self, "板卡设置", "板卡名称不能为空。")
                return
        names = [b["name"] for b in self._boards]
        if len(set(names)) != len(names):
            QtWidgets.QMessageBox.warning(self, "板卡设置", "板卡名称不能重复。")
            return
        self.store.set_boards(self._boards)
        if 0 <= self._idx < len(self._boards):
            self.store.set_active_board(self._boards[self._idx]["name"])
        super().accept()
