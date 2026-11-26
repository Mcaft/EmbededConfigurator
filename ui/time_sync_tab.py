# -*- coding: utf-8 -*-
"""时钟同步（chrony / NTP）与系统时间监测页。"""
import datetime
import time

from PyQt5 import QtCore, QtWidgets

from ui.plot_widget import TimeSeriesPlot


class TimeSyncTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._prev = None           # (host_time, offset)
        self._sampling = False
        self._jump_count = 0
        self._backend = ""
        self._backend_active = False
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        self.tabs.addTab(self._build_sync_tab(), "NTP / chrony 同步")
        self.tabs.addTab(self._build_monitor_tab(), "时间监测（跳变检测）")

    # ---------------- 同步子页 ----------------
    def _build_sync_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)

        top = QtWidgets.QHBoxLayout()
        self.sync_refresh_btn = QtWidgets.QPushButton("刷新状态")
        self.enable_ntp_btn = QtWidgets.QPushButton("启用 NTP")
        self.disable_ntp_btn = QtWidgets.QPushButton("禁用 NTP")
        self.resync_btn = QtWidgets.QPushButton("立即校时")
        self.add_server_btn = QtWidgets.QPushButton("添加 NTP 服务器")
        top.addWidget(self.sync_refresh_btn)
        top.addWidget(self.enable_ntp_btn)
        top.addWidget(self.disable_ntp_btn)
        top.addWidget(self.resync_btn)
        top.addWidget(self.add_server_btn)
        top.addStretch(1)
        lay.addLayout(top)

        self.sync_info = QtWidgets.QPlainTextEdit()
        self.sync_info.setReadOnly(True)
        self.sync_info.setPlaceholderText("点击「刷新状态」查看 NTP / chrony 同步情况。")
        lay.addWidget(self.sync_info, 1)

        self.sync_result = QtWidgets.QLabel("")
        self.sync_result.setWordWrap(True)
        self.sync_result.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lay.addWidget(self.sync_result)

        self.sync_refresh_btn.clicked.connect(self.refresh_sync)
        self.enable_ntp_btn.clicked.connect(lambda: self._run_sync_op("enable"))
        self.disable_ntp_btn.clicked.connect(lambda: self._run_sync_op("disable"))
        self.resync_btn.clicked.connect(lambda: self._run_sync_op("resync"))
        self.add_server_btn.clicked.connect(self._on_add_server)
        return w

    def refresh_sync(self):
        if not self.main.ensure_connected():
            return
        self.sync_refresh_btn.setEnabled(False)
        self.main.run_async(self._gather_sync, self._on_sync, self._on_sync_error)

    def _gather_sync(self):
        client = self.main.timesync
        timedate = client.get_timedatectl()
        service, active = client.detect_backend()
        tracking = client.get_chrony_tracking() if client.is_chrony(service) else None
        sources = client.get_chrony_sources() if client.is_chrony(service) else None
        return timedate, service, active, tracking, sources

    def _on_sync(self, result):
        self.sync_refresh_btn.setEnabled(True)
        timedate, service, active, tracking, sources = result
        self._backend = service
        self._backend_active = active

        lines = ["【后端】" + (f"{service}（{'运行中' if active else '未运行'}）"
                              if service else "未检测到 NTP 服务")]
        for k in ("Local time", "Universal time", "RTC time", "Time zone",
                  "System clock synchronized", "NTP service"):
            if k in timedate:
                lines.append(f"{k}: {timedate[k]}")
        if tracking:
            lines.append("")
            lines.append("【chronyc tracking】")
            lines.extend(f"{k}: {v}" for k, v in tracking.items())
        if sources:
            lines.append("")
            lines.append("【chronyc sources -v】")
            lines.append(sources)
        self.sync_info.setPlainText("\n".join(lines))
        self.main.logger.info("时钟同步状态已刷新")

    def _on_sync_error(self, msg):
        self.sync_refresh_btn.setEnabled(True)
        self.main.show_error("时钟同步", msg)

    def _run_sync_op(self, op):
        if not self.main.ensure_connected():
            return
        self._set_sync_busy(True)
        self.sync_result.setText("正在执行…")
        self.main.run_async(self._do_sync_op, self._on_sync_op_done,
                            self._on_sync_op_error, op)

    def _do_sync_op(self, op):
        client = self.main.timesync
        if op == "enable":
            return client.enable_ntp()
        if op == "disable":
            return client.disable_ntp()
        service, _ = client.detect_backend()
        return client.resync(service)

    def _on_sync_op_done(self, msg):
        self._set_sync_busy(False)
        self.sync_result.setText(msg)
        self.main.logger.info(f"时钟同步操作：{msg}")
        self.refresh_sync()

    def _on_sync_op_error(self, msg):
        self._set_sync_busy(False)
        self.sync_result.setText("")
        self.main.show_error("时钟同步", msg)

    def _on_add_server(self):
        if not self.main.ensure_connected():
            return
        addr, ok = QtWidgets.QInputDialog.getText(
            self, "添加 NTP 服务器", "NTP 服务器地址（如 ntp.aliyun.com）：")
        if not ok or not addr.strip():
            return
        self._set_sync_busy(True)
        self.sync_result.setText("正在添加服务器…")
        self.main.run_async(self.main.timesync.add_chrony_server,
                            self._on_sync_op_done, self._on_sync_op_error, addr.strip())

    def _set_sync_busy(self, busy):
        for b in (self.enable_ntp_btn, self.disable_ntp_btn,
                  self.resync_btn, self.add_server_btn):
            b.setEnabled(not busy)

    # ---------------- 监测子页 ----------------
    def _build_monitor_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)

        top = QtWidgets.QHBoxLayout()
        self.mon_start_btn = QtWidgets.QPushButton("开始监测")
        self.mon_stop_btn = QtWidgets.QPushButton("停止监测")
        self.mon_clear_btn = QtWidgets.QPushButton("清空")
        top.addWidget(self.mon_start_btn)
        top.addWidget(self.mon_stop_btn)
        top.addWidget(self.mon_clear_btn)
        top.addSpacing(16)
        top.addWidget(QtWidgets.QLabel("采样间隔(秒)："))
        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(2)
        top.addWidget(self.interval_spin)
        top.addWidget(QtWidgets.QLabel("跳变阈值(秒)："))
        self.thresh_spin = QtWidgets.QDoubleSpinBox()
        self.thresh_spin.setRange(0.1, 60.0)
        self.thresh_spin.setValue(0.5)
        self.thresh_spin.setSingleStep(0.1)
        top.addWidget(self.thresh_spin)
        top.addStretch(1)
        lay.addLayout(top)

        info = QtWidgets.QHBoxLayout()
        self.mon_offset_label = QtWidgets.QLabel("偏移：-")
        self.mon_drift_label = QtWidgets.QLabel("漂移：-")
        self.mon_time_label = QtWidgets.QLabel("远端时间：-")
        info.addWidget(self.mon_offset_label)
        info.addWidget(self.mon_drift_label)
        info.addWidget(self.mon_time_label)
        info.addStretch(1)
        lay.addLayout(info)

        self.plot = TimeSeriesPlot()
        lay.addWidget(self.plot, 1)

        self.jump_label = QtWidgets.QLabel("跳变事件：0 次")
        lay.addWidget(self.jump_label)
        self.jump_log = QtWidgets.QPlainTextEdit()
        self.jump_log.setReadOnly(True)
        self.jump_log.setMaximumHeight(140)
        self.jump_log.setPlaceholderText("检测到的时间跳变事件会记录在这里。")
        lay.addWidget(self.jump_log)

        self.mon_timer = QtCore.QTimer(self)
        self.mon_timer.timeout.connect(self._sample_tick)

        self.mon_start_btn.clicked.connect(self._start_monitor)
        self.mon_stop_btn.clicked.connect(self._stop_monitor)
        self.mon_clear_btn.clicked.connect(self._clear_monitor)
        self.mon_stop_btn.setEnabled(False)
        return w

    def _start_monitor(self):
        if not self.main.ensure_connected():
            return
        self._prev = None
        self._sampling = False
        self.mon_timer.start(self.interval_spin.value() * 1000)
        self.mon_start_btn.setEnabled(False)
        self.mon_stop_btn.setEnabled(True)
        self.main.logger.info("开始系统时间监测")
        self._sample_tick()

    def _stop_monitor(self):
        self.mon_timer.stop()
        self.mon_start_btn.setEnabled(True)
        self.mon_stop_btn.setEnabled(False)

    def stop_monitoring(self):
        self._stop_monitor()

    def _clear_monitor(self):
        self._prev = None
        self._jump_count = 0
        self.plot.clear()
        self.jump_log.clear()
        self.jump_label.setText("跳变事件：0 次")
        self.mon_offset_label.setText("偏移：-")
        self.mon_drift_label.setText("漂移：-")
        self.mon_time_label.setText("远端时间：-")

    def _sample_tick(self):
        if not self.main.ssh.is_connected():
            return
        if self._sampling:
            return
        self._sampling = True
        self.main.run_async(self._read_sample, self._on_sample, self._on_sample_error)

    def _read_sample(self):
        host_t0 = time.time()
        remote = self.main.timesync.read_remote_time()
        host_t1 = time.time()
        host = (host_t0 + host_t1) / 2.0
        return host, remote

    def _on_sample(self, sample):
        self._sampling = False
        host, remote = sample
        offset = remote - host
        drift = 0.0
        if self._prev is not None:
            phost, poffset = self._prev
            dt = host - phost
            if dt > 0:
                drift = (offset - poffset) / dt * 1e6  # ppm
                delta = offset - poffset
                if abs(delta) >= self.thresh_spin.value():
                    self._record_jump(host, delta)
        self._prev = (host, offset)
        self.plot.add_sample(host, offset)
        self.mon_offset_label.setText(f"偏移：{offset * 1000:+.0f} ms")
        self.mon_drift_label.setText(f"漂移：{drift:+.1f} ppm")
        self.mon_time_label.setText(
            "远端时间：" + datetime.datetime.fromtimestamp(remote).strftime("%H:%M:%S.%f")[:-3])

    def _on_sample_error(self, msg):
        self._sampling = False
        self.main.logger.warn(f"时间采样失败：{msg}")

    def _record_jump(self, t, delta):
        self._jump_count += 1
        self.jump_label.setText(f"跳变事件：{self._jump_count} 次")
        self.plot.add_mark(t)
        ts = datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
        direction = "前跳" if delta > 0 else "后跳"
        self.jump_log.appendPlainText(f"[{ts}] {direction} {delta:+.3f} 秒")
        self.main.logger.warn(f"检测到系统时间跳变：{direction} {delta:+.3f}s @ {ts}")
