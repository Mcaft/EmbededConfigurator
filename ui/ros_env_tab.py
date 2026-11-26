# -*- coding: utf-8 -*-
"""~/.bashrc ROS 环境配置页。"""
from PyQt5 import QtCore, QtWidgets

from core.bashrc import parse_entries

# 未检测到 /opt/ros 时，添加发行版对话框的兜底候选
_FALLBACK_DISTROS = ["noetic", "melodic", "foxy", "galactic", "humble", "iron", "jazzy"]


class RosEnvTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._lines = []              # 完整 ~/.bashrc 行列表（原始）
        self._entries = []            # 当前 ROS source 条目（parse_entries 结果）
        self._removed = set()         # 已删除条目的原始行号
        self._available_distros = []  # /opt/ros 下已安装发行版
        self._loading = False
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        hint = QtWidgets.QLabel(
            "管理 ~/.bashrc 中激活的 ROS 环境。勾选「启用」将在登录时 source 对应环境，"
            "取消勾选则注释掉该行。修改后需点击「保存到 ~/.bashrc」生效。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_row = QtWidgets.QHBoxLayout()
        self.add_distro_btn = QtWidgets.QPushButton("添加 ROS 发行版")
        self.add_ws_btn = QtWidgets.QPushButton("添加工作空间")
        self.refresh_btn = QtWidgets.QPushButton("刷新")
        self.delete_btn = QtWidgets.QPushButton("删除选中")
        self.save_btn = QtWidgets.QPushButton("保存到 ~/.bashrc")
        btn_row.addWidget(self.add_distro_btn)
        btn_row.addWidget(self.add_ws_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["启用", "类型", "路径", "发行版"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        self.result_label = QtWidgets.QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.result_label)

        self.add_distro_btn.clicked.connect(self._on_add_distro)
        self.add_ws_btn.clicked.connect(self._on_add_ws)
        self.delete_btn.clicked.connect(self._on_delete)
        self.refresh_btn.clicked.connect(self.refresh)
        self.save_btn.clicked.connect(self._on_save)

    # ---------------- 加载 ----------------
    def refresh(self):
        if not self.main.ensure_connected():
            return
        self.refresh_btn.setEnabled(False)
        self.main.run_async(self._load, self._on_load, self._on_error)

    def _load(self):
        text = self.main.bashrc.read()
        distros = self.main.bashrc.list_ros_distros()
        return text, distros

    def _on_load(self, result):
        self.refresh_btn.setEnabled(True)
        text, distros = result
        self._lines = text.splitlines()
        self._entries = parse_entries(text)
        self._removed = set()
        self._available_distros = distros or []
        self._populate()
        self.result_label.setText(f"已加载 ~/.bashrc，共 {len(self._entries)} 条 ROS 环境配置")
        self.main.logger.info(f"~/.bashrc 已加载，ROS 环境 {len(self._entries)} 条")

    def _on_error(self, msg):
        self.refresh_btn.setEnabled(True)
        self.main.show_error("ROS 环境", msg)

    # ---------------- 表格 ----------------
    def _populate(self):
        self._loading = True
        self.table.setRowCount(0)
        for e in self._entries:
            self._append_row(e)
        self._loading = False

    def _append_row(self, e):
        row = self.table.rowCount()
        self.table.insertRow(row)
        check = QtWidgets.QTableWidgetItem()
        check.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled
                       | QtCore.Qt.ItemIsSelectable)
        check.setCheckState(QtCore.Qt.Checked if e["active"] else QtCore.Qt.Unchecked)
        check.setData(QtCore.Qt.UserRole, e)
        self.table.setItem(row, 0, check)
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(
            "发行版" if e["is_distro"] else "工作空间"))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(e["path"]))
        self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(e["distro"]))

    def _on_item_changed(self, item):
        if self._loading or item.column() != 0:
            return
        e = item.data(QtCore.Qt.UserRole)
        if e is not None:
            e["active"] = item.checkState() == QtCore.Qt.Checked

    # ---------------- 增删 ----------------
    def _add_entry(self, content, path, distro=""):
        e = {
            "index": -1,  # 新条目：写入时追加到文件末尾
            "active": True,
            "content": content,
            "path": path,
            "distro": distro,
            "is_distro": bool(distro),
        }
        self._entries.append(e)
        self._loading = True
        self._append_row(e)
        self._loading = False

    def _on_add_distro(self):
        distros = self._available_distros or _FALLBACK_DISTROS
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("添加 ROS 发行版")
        form = QtWidgets.QFormLayout(dlg)
        combo = QtWidgets.QComboBox()
        combo.setEditable(True)
        combo.addItems(distros)
        combo.setCurrentText(distros[0])
        form.addRow("发行版（如 noetic / humble）：", combo)
        form.addRow(QtWidgets.QLabel("将添加：source /opt/ros/<发行版>/setup.bash"))
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        distro = combo.currentText().strip()
        if not distro:
            self.main.show_error("ROS 环境", "请填写发行版名称。")
            return
        path = f"/opt/ros/{distro}/setup.bash"
        self._add_entry(f"source {path}", path, distro)

    def _on_add_ws(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("添加工作空间")
        form = QtWidgets.QFormLayout(dlg)
        ws_edit = QtWidgets.QLineEdit("~/catkin_ws")
        ver_combo = QtWidgets.QComboBox()
        ver_combo.addItems(["ROS1（devel/setup.bash）", "ROS2（install/setup.bash）"])
        form.addRow("工作空间路径：", ws_edit)
        form.addRow("ROS 版本：", ver_combo)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        ws = ws_edit.text().strip().rstrip("/")
        if not ws:
            self.main.show_error("ROS 环境", "请填写工作空间路径。")
            return
        sub = "devel" if ver_combo.currentIndex() == 0 else "install"
        path = f"{ws}/{sub}/setup.bash"
        self._add_entry(f"source {path}", path)

    def _on_delete(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            self.main.show_error("ROS 环境", "请先选中要删除的行。")
            return
        for row in rows:
            item = self.table.item(row, 0)
            e = item.data(QtCore.Qt.UserRole) if item else None
            if e is None:
                continue
            if e["index"] >= 0:
                self._removed.add(e["index"])
            self._entries = [x for x in self._entries if x is not e]
            self.table.removeRow(row)

    # ---------------- 保存 ----------------
    def _on_save(self):
        if not self.main.ensure_connected():
            return
        text = self._serialize()
        self.save_btn.setEnabled(False)
        self.result_label.setText("正在保存…")
        self.main.run_async(self.main.bashrc.write, self._on_save_done, self._on_error, text)

    def _serialize(self):
        managed = {e["index"]: e for e in self._entries if e["index"] >= 0}
        appended = [e for e in self._entries if e["index"] < 0]

        lines = []
        for i, line in enumerate(self._lines):
            if i in self._removed:
                continue
            if i in managed:
                e = managed[i]
                lines.append(e["content"] if e["active"] else f"# {e['content']}")
            else:
                lines.append(line)
        for e in appended:
            lines.append(e["content"] if e["active"] else f"# {e['content']}")

        if lines:
            return "\n".join(lines) + "\n"
        return ""

    def _on_save_done(self, _):
        self.save_btn.setEnabled(True)
        self.main.logger.info("~/.bashrc 已更新（原文件已自动备份）")
        self.main.show_info("ROS 环境", "已保存到 ~/.bashrc（原文件已自动备份）。")
        self.refresh()
