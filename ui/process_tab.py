# -*- coding: utf-8 -*-
"""任务管理器（进程列表）页。"""
from PyQt5 import QtCore, QtWidgets


class ProcessTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("刷新")
        self.auto_check = QtWidgets.QCheckBox("自动刷新")
        self.auto_check.setChecked(False)
        self.count_label = QtWidgets.QLabel("")
        top.addWidget(self.refresh_btn)
        top.addWidget(self.auto_check)
        top.addStretch(1)
        top.addWidget(self.count_label)
        layout.addLayout(top)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["PID", "用户", "CPU%", "内存%", "RSS(MB)", "命令"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        hint = QtWidgets.QLabel(
            "CPU% 为进程生命周期内平均占用；按 CPU 占用降序，最多显示前 100 个进程。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self._auto_tick)

        self.refresh_btn.clicked.connect(self.refresh)
        self.auto_check.toggled.connect(self._on_auto_toggled)

    def _on_auto_toggled(self, on):
        if on:
            self.timer.start()
            self.refresh()
        else:
            self.timer.stop()

    def _auto_tick(self):
        if self.main.ssh.is_connected():
            self.refresh()

    def refresh(self):
        if not self.main.ssh.is_connected():
            self._clear()
            return
        self.refresh_btn.setEnabled(False)
        self.main.run_async(self.main.processes.list_processes,
                            self._on_load, self._on_error)

    def _clear(self):
        self.table.setRowCount(0)
        self.count_label.setText("未连接")

    def _on_load(self, procs):
        self.refresh_btn.setEnabled(True)
        self.table.setRowCount(0)
        for p in procs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(p["pid"])))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(p["user"]))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{p['cpu']:.1f}"))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{p['mem']:.1f}"))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{p['rss_mb']:.1f}"))
            cmd_item = QtWidgets.QTableWidgetItem(p["cmd"])
            cmd_item.setToolTip(p["cmd"])
            self.table.setItem(row, 5, cmd_item)
        self.count_label.setText(f"{len(procs)} 个进程")

    def _on_error(self, msg):
        self.refresh_btn.setEnabled(True)
        self.count_label.setText("获取失败")
        self.main.logger.warn(f"获取进程列表失败：{msg}")

    def set_offline(self):
        self._clear()
