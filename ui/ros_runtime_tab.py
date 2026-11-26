# -*- coding: utf-8 -*-
"""ROS 运行页：查询目标设备上运行中的节点 / 话题 / 服务。"""
from PyQt5 import QtCore, QtWidgets

from core.bashrc import parse_entries


class RosRuntimeTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._distros = []
        self._active_distro = ""
        self._ws_paths = []
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        hint = QtWidgets.QLabel(
            "查询目标设备上运行中的 ROS 节点 / 话题 / 服务。程序会自动 source 所选发行版 "
            "的 setup.bash，并可选 source ~/.bashrc 中已启用的工作空间。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("ROS 发行版："))
        self.distro_combo = QtWidgets.QComboBox()
        self.distro_combo.setEditable(True)
        self.distro_combo.setMinimumWidth(160)
        top.addWidget(self.distro_combo)
        self.src_ws_check = QtWidgets.QCheckBox("同时 source 已启用的工作空间")
        self.src_ws_check.setChecked(True)
        top.addWidget(self.src_ws_check)
        self.refresh_env_btn = QtWidgets.QPushButton("刷新环境")
        top.addWidget(self.refresh_env_btn)
        top.addStretch(1)
        layout.addLayout(top)

        btn_row = QtWidgets.QHBoxLayout()
        self.nodes_btn = QtWidgets.QPushButton("节点列表")
        self.topics_btn = QtWidgets.QPushButton("话题列表")
        self.services_btn = QtWidgets.QPushButton("服务列表")
        btn_row.addWidget(self.nodes_btn)
        btn_row.addWidget(self.topics_btn)
        btn_row.addWidget(self.services_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("点击上方按钮查询，结果会显示在这里。")
        layout.addWidget(self.output, 1)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.nodes_btn.clicked.connect(lambda: self._run_query("nodes"))
        self.topics_btn.clicked.connect(lambda: self._run_query("topics"))
        self.services_btn.clicked.connect(lambda: self._run_query("services"))
        self.refresh_env_btn.clicked.connect(self.refresh_env)

    # ---------------- 环境 ----------------
    def refresh_env(self):
        if not self.main.ensure_connected():
            return
        self.refresh_env_btn.setEnabled(False)
        self.main.run_async(self._gather, self._on_env, self._on_error)

    def _gather(self):
        text = self.main.bashrc.read()
        distros = self.main.bashrc.list_ros_distros()
        entries = parse_entries(text)
        active_distro = ""
        ws_paths = []
        for e in entries:
            if not e["active"]:
                continue
            if e["is_distro"]:
                if not active_distro:
                    active_distro = e["distro"]
            else:
                ws_paths.append(e["path"])
        return distros, active_distro, ws_paths

    def _on_env(self, result):
        self.refresh_env_btn.setEnabled(True)
        distros, active_distro, ws_paths = result
        self._distros = distros or []
        self._active_distro = active_distro
        self._ws_paths = ws_paths
        self.distro_combo.clear()
        self.distro_combo.addItems(self._distros)
        if active_distro:
            idx = self.distro_combo.findText(active_distro)
            self.distro_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.status_label.setText(
            f"已加载环境：{len(self._distros)} 个发行版，工作空间 {len(ws_paths)} 个，"
            f"默认发行版 {active_distro or '未检测到'}")
        self.main.logger.info(f"ROS 运行环境已加载：{self._distros or '无'}")

    def _on_error(self, msg):
        self.refresh_env_btn.setEnabled(True)
        self.main.show_error("ROS 运行", msg)

    # ---------------- 查询 ----------------
    def _run_query(self, kind):
        if not self.main.ensure_connected():
            return
        distro = self.distro_combo.currentText().strip()
        ws_paths = self._ws_paths if self.src_ws_check.isChecked() else []
        if not distro:
            self.main.show_error("ROS 运行", "请先选择或填写 ROS 发行版。")
            return
        self._set_busy(True)
        self.output.setPlainText("查询中…")
        self.main.run_async(self._query, self._on_query, self._on_query_error,
                            kind, distro, ws_paths)

    def _query(self, kind, distro, ws_paths):
        runtime = self.main.ros
        if kind == "nodes":
            code, out, _ = runtime.list_nodes(distro, ws_paths)
        elif kind == "topics":
            code, out, _ = runtime.list_topics(distro, ws_paths)
        else:
            code, out, _ = runtime.list_services(distro, ws_paths)
        return kind, code, out

    def _on_query(self, result):
        self._set_busy(False)
        kind, code, out = result
        title = {"nodes": "节点", "topics": "话题", "services": "服务"}[kind]
        if code == 0:
            self.output.setPlainText(out or f"（无{title}）")
            self.status_label.setText(f"{title}查询完成，共 {len(out.splitlines())} 行")
        else:
            self.output.setPlainText(out or "（查询失败，无输出）")
            self.status_label.setText(f"{title}查询失败（退出码 {code}）")

    def _on_query_error(self, msg):
        self._set_busy(False)
        self.main.show_error("ROS 运行", msg)

    def _set_busy(self, busy):
        for b in (self.nodes_btn, self.topics_btn, self.services_btn):
            b.setEnabled(not busy)
