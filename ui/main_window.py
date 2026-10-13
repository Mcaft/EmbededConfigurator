# -*- coding: utf-8 -*-
"""主窗口。"""
from PyQt5 import QtCore, QtWidgets

from core.config import (
    HOST_IP,
    HOST_NETMASK,
    STATUS_POLL_INTERVAL_MS,
)
from core.logger import Logger
from core.orin import OrinClient
from core.rndis import configure_host_ip, detect_rndis_adapter, get_adapter_ip
from core.ssh_client import SSHClient
from core.store import Store
from ui.connection_bar import ConnectionBar
from ui.hotspot_tab import HotspotTab
from ui.ip_tab import IPTab
from ui.status_tab import StatusTab
from ui.wifi_tab import WiFiTab
from ui.worker import Worker


class MainWindow(QtWidgets.QMainWindow):
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Orin NX 地面站配置工具")
        self.resize(940, 780)

        self.store = Store()
        self.logger = Logger()
        self.logger.add_listener(self._on_log_line)
        self.log_signal.connect(self._append_log)

        self.ssh = SSHClient()
        self.orin = OrinClient(self.ssh, self.logger)
        self.thread_pool = QtCore.QThreadPool.globalInstance()

        self._polling = False
        self._reconnecting = False
        self._offline_notified = False
        self._connect_auto = False
        self._rndis_name = None

        self._build_ui()
        self._startup_check()

    # ---------------- UI ----------------
    def _build_ui(self):
        central = QtWidgets.QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)

        self.conn_bar = ConnectionBar()
        self.conn_bar.detect_requested.connect(self._on_detect_rndis)
        self.conn_bar.host_config_requested.connect(self._on_config_host_ip)
        self.conn_bar.connect_requested.connect(self._on_connect)
        self.conn_bar.disconnect_requested.connect(self._on_disconnect)
        self.conn_bar.settings_requested.connect(self._on_settings)
        root.addWidget(self.conn_bar)

        self.tabs = QtWidgets.QTabWidget()
        self.wifi_tab = WiFiTab(self)
        self.ip_tab = IPTab(self)
        self.hotspot_tab = HotspotTab(self)
        self.status_tab = StatusTab()
        self.tabs.addTab(self.wifi_tab, "WiFi 配置")
        self.tabs.addTab(self.ip_tab, "IP 配置")
        self.tabs.addTab(self.hotspot_tab, "热点配置")
        self.tabs.addTab(self.status_tab, "状态显示")
        root.addWidget(self.tabs, 1)

        self.status_tab.refresh_requested.connect(self.request_status_refresh)

        log_group = QtWidgets.QGroupBox("日志")
        log_lay = QtWidgets.QVBoxLayout(log_group)
        self.log_edit = QtWidgets.QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(2000)
        log_lay.addWidget(self.log_edit)
        log_group.setMaximumHeight(180)
        root.addWidget(log_group)

        self.status_timer = QtCore.QTimer(self)
        self.status_timer.timeout.connect(self._poll_status)

        self._set_tabs_enabled(False)

    def _set_tabs_enabled(self, enabled):
        # 前三个功能页需连接后才可用，状态页始终可见
        for i in range(3):
            self.tabs.widget(i).setEnabled(enabled)

    # ---------------- 日志 ----------------
    def _on_log_line(self, line):
        self.log_signal.emit(line)

    def _append_log(self, line):
        self.log_edit.appendPlainText(line)

    # ---------------- 通用 ----------------
    def run_async(self, fn, on_done=None, on_error=None, *args, **kwargs):
        worker = Worker(fn, *args, **kwargs)
        if on_done is not None:
            worker.signals.finished.connect(on_done)
        if on_error is not None:
            worker.signals.error.connect(on_error)
        else:
            worker.signals.error.connect(self._on_generic_error)
        self.thread_pool.start(worker)
        return worker

    def _on_generic_error(self, msg):
        self.logger.error(msg)
        QtWidgets.QMessageBox.warning(self, "操作失败", msg)

    def show_error(self, title, msg):
        self.logger.error(f"{title}: {msg}")
        QtWidgets.QMessageBox.warning(self, title, msg)

    def show_info(self, title, msg):
        self.logger.info(f"{title}: {msg}")
        QtWidgets.QMessageBox.information(self, title, msg)

    def ensure_connected(self):
        if self.ssh.is_connected():
            return True
        QtWidgets.QMessageBox.information(self, "未连接", "请先连接到 Orin NX。")
        return False

    # ---------------- RNDIS ----------------
    def _startup_check(self):
        self.logger.info("程序启动，开始检测 RNDIS 网卡…")
        self.run_async(self._detect_rndis_task, self._on_rndis_detected, self._on_rndis_error)

    def _detect_rndis_task(self):
        adapter = detect_rndis_adapter()
        if adapter is None:
            return None
        adapter["ip"] = get_adapter_ip(adapter["name"])
        return adapter

    def _on_rndis_detected(self, adapter):
        if adapter is None:
            self.conn_bar.set_rndis_status("未检测到")
            self.conn_bar.set_host_ip("-")
            self.logger.warn("未检测到 RNDIS 网卡，请确认 USB 数据线已连接并安装 RNDIS 驱动。")
            QtWidgets.QMessageBox.warning(
                self, "未检测到 RNDIS",
                "未检测到 RNDIS 网卡。\n\n请检查：\n"
                "1. USB 数据线是否连接到 Orin NX 的 Device 模式 Type-C 口；\n"
                "2. Windows 是否正确识别了 RNDIS 设备（可能需要安装 RNDIS 驱动）。")
            return
        self._rndis_name = adapter["name"]
        self.conn_bar.set_rndis_status(f"{adapter['name']}（{adapter['status']}）")
        ip = adapter.get("ip", "")
        self.conn_bar.set_host_ip(ip or "未配置")
        if ip == HOST_IP:
            self.logger.info(f"RNDIS 网卡 {adapter['name']} 本机 IP 已正确配置为 {HOST_IP}")
            self._on_connect(auto=True)
        else:
            self.logger.warn(f"本机 IP 当前为 {ip or '空'}，需要配置为 {HOST_IP}")
            ret = QtWidgets.QMessageBox.question(
                self, "配置本机 IP",
                f"检测到 RNDIS 网卡，但本机 IP 不是 {HOST_IP}（当前：{ip or '未配置'}）。\n\n"
                f"是否现在配置为 {HOST_IP}？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if ret == QtWidgets.QMessageBox.Yes:
                self._on_config_host_ip()

    def _on_rndis_error(self, msg):
        self.conn_bar.set_rndis_status("检测失败")
        self.logger.error(f"RNDIS 检测失败：{msg}")

    def _on_detect_rndis(self):
        self.run_async(self._detect_rndis_task, self._on_rndis_detected, self._on_rndis_error)

    def _on_config_host_ip(self):
        if not self._rndis_name:
            self.run_async(self._detect_rndis_task, self._on_rndis_then_config, self._on_rndis_error)
            return
        ok, msg = configure_host_ip(self._rndis_name, HOST_IP, HOST_NETMASK)
        if ok:
            self.logger.info(msg)
            QtWidgets.QMessageBox.information(self, "配置本机 IP", msg)
        else:
            self.show_error("配置本机 IP 失败", msg)
        self.run_async(lambda: get_adapter_ip(self._rndis_name), self._on_host_ip_refreshed)

    def _on_rndis_then_config(self, adapter):
        if adapter is None:
            self._on_rndis_detected(None)
            return
        self._on_rndis_detected(adapter)
        self._on_config_host_ip()

    def _on_host_ip_refreshed(self, ip):
        self.conn_bar.set_host_ip(ip or "未配置")

    # ---------------- 连接 ----------------
    def _on_connect(self, auto=False):
        if self.ssh.is_connected():
            return
        host = self.store.get("ssh_host", "192.168.55.1")
        port = int(self.store.get("ssh_port", 22))
        user = self.store.get("ssh_username", "nvidia")
        pwd = self.store.get("ssh_password", "nvidia")
        self._connect_auto = auto
        self.conn_bar.set_ssh_state("connecting")
        self.logger.info(f"正在连接 {user}@{host}:{port} …")
        self.run_async(lambda: self.ssh.connect(host, port, user, pwd),
                       self._on_connected, self._on_connect_error)

    def _on_connected(self, _):
        self.conn_bar.set_ssh_state("connected", self.ssh.host)
        self.logger.info("SSH 连接成功")
        self._set_tabs_enabled(True)
        self._offline_notified = False
        self._reconnecting = False
        self._start_polling()
        self.ip_tab.refresh()
        self.wifi_tab.refresh_saved()
        self.request_status_refresh()

    def _on_connect_error(self, msg):
        self.conn_bar.set_ssh_state("disconnected", "连接失败")
        self.logger.error(f"SSH 连接失败：{msg}")
        if not self._connect_auto:
            QtWidgets.QMessageBox.warning(
                self, "连接失败",
                f"无法连接到 Orin NX。\n\n{msg}\n\n请确认：\n"
                f"1. RNDIS 网卡已识别且本机 IP 为 {HOST_IP}；\n"
                "2. Orin NX 已开机并完成初始化（OOBE），SSH 服务已启动。")

    def _on_disconnect(self):
        self._stop_polling()
        self.ssh.disconnect()
        self.conn_bar.set_ssh_state("disconnected")
        self._set_tabs_enabled(False)
        self.status_tab.set_offline()
        self.logger.info("已断开连接")

    # ---------------- 状态轮询 ----------------
    def _start_polling(self):
        self.status_timer.start(STATUS_POLL_INTERVAL_MS)

    def _stop_polling(self):
        self.status_timer.stop()

    def request_status_refresh(self):
        self._poll_status()

    def _poll_status(self):
        if self._polling:
            return
        if not self.ssh.is_connected():
            self._try_reconnect()
            return
        self._polling = True
        self.run_async(self.orin.get_status, self._on_status, self._on_status_error)

    def _on_status(self, status):
        self._polling = False
        if self._offline_notified:
            self._offline_notified = False
            self.logger.info("已恢复连接")
        self.status_tab.update_status(status)

    def _on_status_error(self, msg):
        self._polling = False
        if not self.ssh.is_connected():
            self._handle_disconnected(msg)
        else:
            self.logger.warn(f"获取状态失败：{msg}")

    def _handle_disconnected(self, reason):
        self.status_tab.set_offline()
        if not self._offline_notified:
            self._offline_notified = True
            self.logger.warn(f"连接已断开（{reason}），尝试自动重连…")
            self.conn_bar.set_ssh_state("disconnected", "已断开")
            self._set_tabs_enabled(False)

    def _try_reconnect(self):
        if self._reconnecting:
            return
        self._reconnecting = True
        host = self.store.get("ssh_host", "192.168.55.1")
        port = int(self.store.get("ssh_port", 22))
        user = self.store.get("ssh_username", "nvidia")
        pwd = self.store.get("ssh_password", "nvidia")

        def task():
            self.ssh.connect(host, port, user, pwd)
            return True

        def done(_):
            self._reconnecting = False
            self._on_connected(None)

        def error(msg):
            self._reconnecting = False
            self._handle_disconnected(msg)

        self.run_async(task, done, error)

    # ---------------- 设置 ----------------
    def _on_settings(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("连接设置")
        form = QtWidgets.QFormLayout(dlg)
        host_edit = QtWidgets.QLineEdit(str(self.store.get("ssh_host", "192.168.55.1")))
        port_edit = QtWidgets.QLineEdit(str(self.store.get("ssh_port", 22)))
        user_edit = QtWidgets.QLineEdit(str(self.store.get("ssh_username", "nvidia")))
        pwd_edit = QtWidgets.QLineEdit(str(self.store.get("ssh_password", "nvidia")))
        pwd_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("主机地址：", host_edit)
        form.addRow("端口：", port_edit)
        form.addRow("用户名：", user_edit)
        form.addRow("密码：", pwd_edit)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        self.store.set("ssh_host", host_edit.text().strip() or "192.168.55.1")
        try:
            self.store.set("ssh_port", int(port_edit.text().strip()))
        except ValueError:
            self.store.set("ssh_port", 22)
        self.store.set("ssh_username", user_edit.text().strip() or "nvidia")
        self.store.set("ssh_password", pwd_edit.text())
        self.logger.info("连接设置已保存")
