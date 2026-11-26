# -*- coding: utf-8 -*-
"""systemd 服务管理页。"""
from PyQt5 import QtCore, QtWidgets


class ServicesTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._units = []
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        hint = QtWidgets.QLabel(
            "管理目标设备上的 systemd 服务（启动 / 停止 / 重启 / 启用 / 禁用）。"
            "适用于让 ROS 节点开机自启等场景。启用/禁用与系统服务通常需要 sudo 权限。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("过滤："))
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("输入关键字（如 ros、gps、camera）")
        top.addWidget(self.filter_edit, 1)
        self.sudo_check = QtWidgets.QCheckBox("使用 sudo")
        self.sudo_check.setChecked(True)
        top.addWidget(self.sudo_check)
        self.refresh_btn = QtWidgets.QPushButton("刷新")
        top.addWidget(self.refresh_btn)
        layout.addLayout(top)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["服务", "状态", "子状态", "描述"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        btn_row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("启动")
        self.stop_btn = QtWidgets.QPushButton("停止")
        self.restart_btn = QtWidgets.QPushButton("重启")
        self.enable_btn = QtWidgets.QPushButton("启用")
        self.disable_btn = QtWidgets.QPushButton("禁用")
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.restart_btn)
        btn_row.addWidget(self.enable_btn)
        btn_row.addWidget(self.disable_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.result_label = QtWidgets.QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.result_label)

        self.refresh_btn.clicked.connect(self.refresh)
        self.start_btn.clicked.connect(lambda: self._run_action("start"))
        self.stop_btn.clicked.connect(lambda: self._run_action("stop"))
        self.restart_btn.clicked.connect(lambda: self._run_action("restart"))
        self.enable_btn.clicked.connect(lambda: self._run_action("enable"))
        self.disable_btn.clicked.connect(lambda: self._run_action("disable"))

    # ---------------- 加载 ----------------
    def refresh(self):
        if not self.main.ensure_connected():
            return
        self.refresh_btn.setEnabled(False)
        self.main.run_async(self._load, self._on_load, self._on_error)

    def _load(self):
        return self.main.services.list_units(self.filter_edit.text().strip())

    def _on_load(self, units):
        self.refresh_btn.setEnabled(True)
        self._units = units
        self.table.setRowCount(0)
        for u in units:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(u["unit"]))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(u["active"]))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(u["sub"]))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(u["description"]))
        self.result_label.setText(f"共 {len(units)} 个服务")
        self.main.logger.info(f"systemd 服务列表已刷新，共 {len(units)} 个")

    def _on_error(self, msg):
        self.refresh_btn.setEnabled(True)
        self.main.show_error("系统服务", msg)

    # ---------------- 操作 ----------------
    def _selected_unit(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        if len(rows) != 1:
            self.main.show_error("系统服务", "请选中一个服务。")
            return None
        row = next(iter(rows))
        if not 0 <= row < len(self._units):
            return None
        return self._units[row]["unit"]

    def _run_action(self, action):
        unit = self._selected_unit()
        if not unit:
            return
        if not self.main.ensure_connected():
            return
        use_sudo = self.sudo_check.isChecked()
        self._set_busy(True)
        self.result_label.setText(f"正在 {action} {unit} …")
        self.main.run_async(self.main.services.action,
                            self._on_action_done, self._on_action_error,
                            unit, action, use_sudo)

    def _on_action_done(self, msg):
        self._set_busy(False)
        self.result_label.setText(msg)
        self.main.logger.info(f"systemd：{msg}")
        self.refresh()

    def _on_action_error(self, msg):
        self._set_busy(False)
        self.result_label.setText("")
        self.main.show_error("系统服务", msg)

    def _set_busy(self, busy):
        for b in (self.start_btn, self.stop_btn, self.restart_btn,
                  self.enable_btn, self.disable_btn):
            b.setEnabled(not busy)
