# -*- coding: utf-8 -*-
"""状态显示页。"""
import datetime

from PyQt5 import QtCore, QtWidgets

from core.config import STATUS_POLL_INTERVAL_MS


class StatusTab(QtWidgets.QWidget):
    refresh_requested = QtCore.pyqtSignal()
    auto_toggled = QtCore.pyqtSignal(bool)
    interval_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("手动刷新")
        self.auto_check = QtWidgets.QCheckBox("自动刷新")
        self.auto_check.setChecked(True)
        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(STATUS_POLL_INTERVAL_MS // 1000)
        self.interval_spin.setSuffix(" 秒")
        self.last_update = QtWidgets.QLabel("")
        top.addWidget(self.refresh_btn)
        top.addWidget(self.auto_check)
        top.addWidget(self.interval_spin)
        top.addStretch(1)
        top.addWidget(self.last_update)
        layout.addLayout(top)

        form = QtWidgets.QGridLayout()
        row = 0

        form.addWidget(QtWidgets.QLabel("IP 地址："), row, 0, QtCore.Qt.AlignTop)
        self.ip_label = QtWidgets.QLabel("-")
        self.ip_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.ip_label.setWordWrap(True)
        form.addWidget(self.ip_label, row, 1)
        row += 1

        form.addWidget(QtWidgets.QLabel("WiFi 状态："), row, 0, QtCore.Qt.AlignTop)
        self.wifi_label = QtWidgets.QLabel("-")
        self.wifi_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.wifi_label.setWordWrap(True)
        form.addWidget(self.wifi_label, row, 1)
        row += 1

        form.addWidget(QtWidgets.QLabel("CPU 占用："), row, 0)
        self.cpu_bar = QtWidgets.QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_label = QtWidgets.QLabel("")
        cpu_row = QtWidgets.QHBoxLayout()
        cpu_row.addWidget(self.cpu_bar)
        cpu_row.addWidget(self.cpu_label)
        form.addLayout(cpu_row, row, 1)
        row += 1

        form.addWidget(QtWidgets.QLabel("内存占用："), row, 0)
        self.mem_bar = QtWidgets.QProgressBar()
        self.mem_bar.setRange(0, 100)
        self.mem_label = QtWidgets.QLabel("")
        mem_row = QtWidgets.QHBoxLayout()
        mem_row.addWidget(self.mem_bar)
        mem_row.addWidget(self.mem_label)
        form.addLayout(mem_row, row, 1)
        row += 1

        form.addWidget(QtWidgets.QLabel("温度："), row, 0, QtCore.Qt.AlignTop)
        self.temp_label = QtWidgets.QLabel("-")
        self.temp_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.temp_label.setWordWrap(True)
        form.addWidget(self.temp_label, row, 1)
        row += 1

        form.addWidget(QtWidgets.QLabel("GPU / 功耗："), row, 0, QtCore.Qt.AlignTop)
        self.gpu_label = QtWidgets.QLabel("-")
        self.gpu_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.gpu_label.setWordWrap(True)
        form.addWidget(self.gpu_label, row, 1)
        row += 1

        form.addWidget(QtWidgets.QLabel("磁盘占用："), row, 0)
        self.disk_bar = QtWidgets.QProgressBar()
        self.disk_bar.setRange(0, 100)
        self.disk_label = QtWidgets.QLabel("")
        disk_row = QtWidgets.QHBoxLayout()
        disk_row.addWidget(self.disk_bar)
        disk_row.addWidget(self.disk_label)
        form.addLayout(disk_row, row, 1)
        row += 1

        form.addWidget(QtWidgets.QLabel("运行时间："), row, 0, QtCore.Qt.AlignTop)
        self.uptime_label = QtWidgets.QLabel("-")
        self.uptime_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.uptime_label.setWordWrap(True)
        form.addWidget(self.uptime_label, row, 1)
        row += 1

        form.setColumnStretch(1, 1)
        layout.addLayout(form)
        layout.addStretch(1)

        self.refresh_btn.clicked.connect(self.refresh_requested)
        self.auto_check.toggled.connect(self.auto_toggled)
        self.interval_spin.valueChanged.connect(self.interval_changed)

    def update_status(self, status):
        if status.get("ips"):
            self.ip_label.setText("\n".join(
                f"{i['interface']}: {i['ip']}/{i['prefix']}" for i in status["ips"]))
        else:
            self.ip_label.setText("（无 IPv4 地址）")

        wifi_lines = []
        for d in status.get("wifi", []):
            conn = f" → {d['connection']}" if d["connection"] else ""
            wifi_lines.append(f"{d['device']} ({d['type']}): {d['state']}{conn}")
        self.wifi_label.setText("\n".join(wifi_lines) if wifi_lines else "（无设备信息）")

        cpu = status.get("cpu")
        if cpu:
            self.cpu_bar.setValue(int(round(cpu["usage"])))
            parts = [f"{cpu['usage']}%"]
            if cpu.get("user") is not None:
                parts.append(f"用户 {cpu['user']}%")
            if cpu.get("system") is not None:
                parts.append(f"系统 {cpu['system']}%")
            if cpu.get("wait") is not None:
                parts.append(f"IO等待 {cpu['wait']}%")
            self.cpu_label.setText("  ".join(parts))
        else:
            self.cpu_bar.setValue(0)
            self.cpu_label.setText("")

        mem = status.get("memory")
        if mem:
            self.mem_bar.setValue(int(round(mem["percent"])))
            self.mem_label.setText(f"{mem['used_mb']} / {mem['total_mb']} MB ({mem['percent']}%)")
        else:
            self.mem_bar.setValue(0)
            self.mem_label.setText("")

        temps = status.get("temperatures", [])
        if temps:
            self.temp_label.setText("\n".join(
                f"{t['name']}: {t['celsius']:.1f} ℃" for t in temps))
        else:
            self.temp_label.setText("（无温度数据）")

        gpu = status.get("gpu")
        if gpu:
            parts = []
            if gpu.get("gpu") is not None:
                parts.append(f"GPU {gpu['gpu']}%")
            if gpu.get("emc") is not None:
                parts.append(f"EMC {gpu['emc']}%")
            if gpu.get("power") is not None:
                parts.append(f"功耗 {gpu['power']} mW")
            if gpu.get("temp") is not None:
                parts.append(f"GPU温度 {gpu['temp']:.1f} ℃")
            self.gpu_label.setText("  ".join(parts) if parts else "（无法解析 GPU 数据）")
        else:
            self.gpu_label.setText("（tegrastats 不可用）")

        disk = status.get("disk")
        if disk:
            pct = disk["percent"].rstrip("%")
            try:
                pv = int(round(float(pct)))
            except ValueError:
                pv = 0
            self.disk_bar.setValue(pv)
            self.disk_label.setText(f"{disk['used']} / {disk['size']} ({disk['percent']})")
        else:
            self.disk_bar.setValue(0)
            self.disk_label.setText("")

        self.uptime_label.setText(status.get("uptime") or "-")
        self.last_update.setText("更新于 " + datetime.datetime.now().strftime("%H:%M:%S"))

    def set_offline(self):
        self.ip_label.setText("-")
        self.wifi_label.setText("离线")
        self.cpu_bar.setValue(0)
        self.cpu_label.setText("")
        self.mem_bar.setValue(0)
        self.mem_label.setText("")
        self.temp_label.setText("-")
        self.gpu_label.setText("-")
        self.disk_bar.setValue(0)
        self.disk_label.setText("")
        self.uptime_label.setText("-")
