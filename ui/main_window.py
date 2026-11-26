# -*- coding: utf-8 -*-
"""主窗口。"""
import shutil

from PyQt5 import QtCore, QtWidgets

from core.bashrc import BashrcManager
from core.config import (
    APP_NAME,
    HOST_IP,
    HOST_NETMASK,
    LOG_FILE,
    MODE_RNDIS,
    STATUS_POLL_INTERVAL_MS,
)
from core.logger import Logger
from core.orin import OrinClient
from core.processes import ProcessManager
from core.rndis import configure_host_ip, detect_rndis_adapter, get_adapter_ip
from core.ros import RosRuntime
from core.services import ServiceManager
from core.ssh_client import SSHClient
from core.store import Store
from core.timesync import TimeSyncClient
from ui.board_dialog import BoardDialog
from ui.connection_bar import ConnectionBar
from ui.hotspot_tab import HotspotTab
from ui.ip_tab import IPTab
from ui.process_tab import ProcessTab
from ui.ros_env_tab import RosEnvTab
from ui.ros_runtime_tab import RosRuntimeTab
from ui.services_tab import ServicesTab
from ui.status_tab import StatusTab
from ui.time_sync_tab import TimeSyncTab
from ui.wifi_tab import WiFiTab
from ui.worker import Worker


class MainWindow(QtWidgets.QMainWindow):
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Orin NX 地面站配置工具")
        self.resize(940, 780)

        self.store = Store()
        self.logger = Logger()
        self.logger.add_listener(self._on_log_line)
        self.log_signal.connect(self._append_log)

        self.ssh = SSHClient()
        self.orin = OrinClient(self.ssh, self.logger)
        self.bashrc = BashrcManager(self.ssh, self.logger)
        self.ros = RosRuntime(self.ssh, self.logger)
        self.services = ServiceManager(self.ssh, self.logger)
        self.processes = ProcessManager(self.ssh, self.logger)
        self.timesync = TimeSyncClient(self.ssh, self.logger)
        self.thread_pool = QtCore.QThreadPool.globalInstance()

        self._polling = False
        self._reconnecting = False
        self._offline_notified = False
        self._connect_auto = False
        self._rndis_name = None
        self._updating_boards = False
        self._auto_refresh = True
        self._poll_interval_ms = STATUS_POLL_INTERVAL_MS

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
        self.conn_bar.board_changed.connect(self._on_board_selected)
        root.addWidget(self.conn_bar)

        # 左侧导航栏 + 页面栈
        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav = QtWidgets.QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFixedWidth(160)
        self.nav.setFocusPolicy(QtCore.Qt.NoFocus)
        body.addWidget(self.nav)

        self.pages = QtWidgets.QStackedWidget()

        # 网络配置页（内含 WiFi / IP / 热点 子标签）
        self.network_page = QtWidgets.QWidget()
        net_lay = QtWidgets.QVBoxLayout(self.network_page)
        net_lay.setContentsMargins(0, 0, 0, 0)
        self.net_tabs = QtWidgets.QTabWidget()
        self.wifi_tab = WiFiTab(self)
        self.ip_tab = IPTab(self)
        self.hotspot_tab = HotspotTab(self)
        self.net_tabs.addTab(self.wifi_tab, "WiFi 配置")
        self.net_tabs.addTab(self.ip_tab, "IP 配置")
        self.net_tabs.addTab(self.hotspot_tab, "热点配置")
        net_lay.addWidget(self.net_tabs)
        self.pages.addWidget(self.network_page)

        # ROS 环境页
        self.ros_tab = RosEnvTab(self)
        self.pages.addWidget(self.ros_tab)

        # ROS 运行页
        self.ros_runtime_tab = RosRuntimeTab(self)
        self.pages.addWidget(self.ros_runtime_tab)

        # 系统服务页
        self.services_tab = ServicesTab(self)
        self.pages.addWidget(self.services_tab)

        # 时钟同步页
        self.time_sync_tab = TimeSyncTab(self)
        self.pages.addWidget(self.time_sync_tab)

        # 状态显示页（系统状态 + 任务管理器）
        self.status_tab = StatusTab()
        self.process_tab = ProcessTab(self)
        self.status_page = QtWidgets.QTabWidget()
        self.status_page.addTab(self.status_tab, "系统状态")
        self.status_page.addTab(self.process_tab, "任务管理器")
        self.pages.addWidget(self.status_page)

        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)

        self.nav.addItem("网络配置")
        self.nav.addItem("ROS 环境")
        self.nav.addItem("ROS 运行")
        self.nav.addItem("系统服务")
        self.nav.addItem("时钟同步")
        self.nav.addItem("状态显示")
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self.status_tab.refresh_requested.connect(self.request_status_refresh)
        self.status_tab.auto_toggled.connect(self._on_auto_refresh_toggled)
        self.status_tab.interval_changed.connect(self._on_interval_changed)

        log_group = QtWidgets.QGroupBox("日志")
        log_lay = QtWidgets.QVBoxLayout(log_group)
        self.log_edit = QtWidgets.QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(2000)
        log_lay.addWidget(self.log_edit)
        log_btns = QtWidgets.QHBoxLayout()
        self.clear_log_btn = QtWidgets.QPushButton("清空日志")
        self.export_log_btn = QtWidgets.QPushButton("导出日志")
        log_btns.addStretch(1)
        log_btns.addWidget(self.clear_log_btn)
        log_btns.addWidget(self.export_log_btn)
        log_lay.addLayout(log_btns)
        self.clear_log_btn.clicked.connect(self.log_edit.clear)
        self.export_log_btn.clicked.connect(self._export_log)
        log_group.setMaximumHeight(200)
        root.addWidget(log_group)

        self.status_timer = QtCore.QTimer(self)
        self.status_timer.timeout.connect(self._poll_status)

        self._set_tabs_enabled(False)
        self._populate_boards()

    def _set_tabs_enabled(self, enabled):
        # 网络配置 / ROS 环境 / ROS 运行 / 系统服务 / 时钟同步需连接后才可用，
        # 状态页（含任务管理器）始终可见
        self.network_page.setEnabled(enabled)
        self.ros_tab.setEnabled(enabled)
        self.ros_runtime_tab.setEnabled(enabled)
        self.services_tab.setEnabled(enabled)
        self.time_sync_tab.setEnabled(enabled)

    # ---------------- 板卡 ----------------
    def _populate_boards(self):
        self._updating_boards = True
        try:
            self.conn_bar.set_boards(
                [b["name"] for b in self.store.get_boards()],
                self.store.get_active_board_name())
        finally:
            self._updating_boards = False
        self._apply_active_board_ui()

    def _apply_active_board_ui(self):
        board = self.store.get_active_board()
        if board is not None:
            self.conn_bar.apply_board(board)

    def _on_board_selected(self, name):
        if self._updating_boards:
            return
        self.store.set_active_board(name)
        self._apply_active_board_ui()
        if self.ssh.is_connected():
            self.logger.info(f"已切换板卡：{name}，断开原连接")
            self._on_disconnect()
        else:
            self.logger.info(f"当前板卡：{name}")

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
        board = self.store.get_active_board()
        if board and board.get("mode") == MODE_RNDIS:
            self.logger.info("程序启动，开始检测 RNDIS 网卡…")
            self.run_async(self._detect_rndis_task, self._on_rndis_detected, self._on_rndis_error)
        else:
            self.logger.info("当前为局域网连接模式，跳过 RNDIS 检测。")

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
        board = self.store.get_active_board()
        if board is None:
            self.conn_bar.set_ssh_state("disconnected", "无板卡配置")
            QtWidgets.QMessageBox.warning(
                self, "连接失败", "没有板卡配置，请在「设置」中添加板卡。")
            return
        host = board.get("ssh_host") or ""
        if not host:
            self.conn_bar.set_ssh_state("disconnected", "未填写 IP")
            QtWidgets.QMessageBox.warning(
                self, "连接失败", "当前板卡未填写 SSH IP，请在「设置」中填写。")
            return
        port = int(board.get("ssh_port", 22))
        user = board.get("ssh_username", "")
        pwd = board.get("ssh_password", "")
        self._connect_auto = auto
        self.conn_bar.set_ssh_state("connecting")
        self.logger.info(f"正在连接 {user}@{host}:{port}（板卡：{board['name']}）…")
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
        self.ros_tab.refresh()
        self.ros_runtime_tab.refresh_env()
        self.services_tab.refresh()
        self.time_sync_tab.refresh_sync()
        self.process_tab.refresh()
        self.request_status_refresh()

    def _on_connect_error(self, msg):
        self.conn_bar.set_ssh_state("disconnected", "连接失败")
        self.logger.error(f"SSH 连接失败：{msg}")
        if self._connect_auto:
            return
        board = self.store.get_active_board()
        if board and board.get("mode") == MODE_RNDIS:
            hint = (f"1. RNDIS 网卡已识别且本机 IP 为 {HOST_IP}；\n"
                    "2. 板卡已开机并完成初始化（OOBE），SSH 服务已启动。")
        else:
            hint = ("1. 板卡与上位机在同一局域网，且 IP / 账号密码填写正确；\n"
                    "2. 板卡已开机并完成初始化（OOBE），SSH 服务已启动。")
        QtWidgets.QMessageBox.warning(
            self, "连接失败",
            f"无法连接到板卡。\n\n{msg}\n\n请确认：\n{hint}")

    def _on_disconnect(self):
        self._stop_polling()
        self.time_sync_tab.stop_monitoring()
        self.ssh.disconnect()
        self.conn_bar.set_ssh_state("disconnected")
        self._set_tabs_enabled(False)
        self.status_tab.set_offline()
        self.process_tab.set_offline()
        self.logger.info("已断开连接")

    # ---------------- 状态轮询 ----------------
    def _start_polling(self):
        self.status_timer.start(self._poll_interval_ms)

    def _stop_polling(self):
        self.status_timer.stop()

    def request_status_refresh(self):
        self._fetch_status()

    def _poll_status(self):
        if self._polling:
            return
        if not self.ssh.is_connected():
            self._try_reconnect()
            return
        if not self._auto_refresh:
            return
        self._fetch_status()

    def _fetch_status(self):
        if self._polling:
            return
        self._polling = True
        self.run_async(self.orin.get_status, self._on_status, self._on_status_error)

    def _on_auto_refresh_toggled(self, enabled):
        self._auto_refresh = enabled
        self.logger.info("自动刷新已开启" if enabled else "自动刷新已关闭")
        if enabled and self.ssh.is_connected():
            self._fetch_status()

    def _on_interval_changed(self, secs):
        self._poll_interval_ms = secs * 1000
        self.status_timer.setInterval(self._poll_interval_ms)

    def _export_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出日志", "embededconfigurator.log",
            "日志文件 (*.log);;文本文件 (*.txt);;所有文件 (*)")
        if not path:
            return
        try:
            shutil.copyfile(LOG_FILE, path)
            self.logger.info(f"日志已导出到 {path}")
            QtWidgets.QMessageBox.information(self, "导出日志", f"日志已导出到：\n{path}")
        except OSError as e:
            self.show_error("导出日志失败", str(e))

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
        board = self.store.get_active_board()
        if board is None or not (board.get("ssh_host") or ""):
            return
        self._reconnecting = True
        host = board.get("ssh_host")
        port = int(board.get("ssh_port", 22))
        user = board.get("ssh_username", "")
        pwd = board.get("ssh_password", "")

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
        dlg = BoardDialog(self.store, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self._populate_boards()
            self.logger.info("板卡设置已保存")
