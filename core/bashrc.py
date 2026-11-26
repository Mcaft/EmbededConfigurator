# -*- coding: utf-8 -*-
"""远程 ~/.bashrc 的读取/写入，以及 ROS 环境 source 行的解析。"""
import base64
import re
import shlex

from core.config import CMD_TIMEOUT

# ROS 环境脚本通常以 (local_)setup.bash/.sh/.zsh 结尾
SETUP_SUFFIX_RE = re.compile(r"(?:local_)?setup\.(?:bash|sh|zsh)$")
SOURCE_RE = re.compile(
    r'^\s*(?P<cmd>source|\.)\s+'
    r'(?P<path>["\']?[^\s"\']+["\']?)(?P<tail>.*)$')
DISTRO_RE = re.compile(r"/opt/ros/([^/]+)/")


def parse_entries(text):
    """从 ~/.bashrc 文本中解析出 ROS 环境 source 行。

    返回条目列表，每项：
      index    - 该行在文件中的行号（0 起）
      active   - 是否激活（未被注释）
      content  - 去掉行首空白与 # 注释后的“激活形态”文本
      path     - source 的脚本路径
      distro   - 若为 /opt/ros/<发行版>/setup.* 则为其发行版名，否则空
      is_distro- 是否 ROS 发行版
    """
    entries = []
    for idx, raw in enumerate(text.splitlines()):
        line = raw.rstrip("\r")
        stripped = line.lstrip()
        if not stripped:
            continue
        active_line = re.sub(r"^\s*#+\s*", "", line).rstrip()
        m = SOURCE_RE.match(active_line)
        if not m:
            continue
        path = m.group("path").strip("\"'")
        if not SETUP_SUFFIX_RE.search(path):
            continue
        dm = DISTRO_RE.search(path)
        distro = dm.group(1) if dm else ""
        entries.append({
            "index": idx,
            "active": not stripped.startswith("#"),
            "content": active_line,
            "path": path,
            "distro": distro,
            "is_distro": bool(distro),
        })
    return entries


class BashrcManager:
    """通过 SSH 读写目标设备（Orin NX）的 ~/.bashrc。"""

    def __init__(self, ssh, logger=None):
        self.ssh = ssh
        self.logger = logger

    def _run(self, cmd, timeout=CMD_TIMEOUT, log=True):
        code, out, err = self.ssh.exec_command(cmd, timeout=timeout)
        if log and self.logger:
            self.logger.debug(f"SSH: {cmd}")
        return code, out, err

    def read(self):
        # 文件不存在时返回空串，便于后续创建
        code, out, err = self._run("cat ~/.bashrc 2>/dev/null || true")
        if code is None:
            raise RuntimeError(err or "读取 ~/.bashrc 失败")
        return out

    def list_ros_distros(self):
        """返回 /opt/ros 下已安装的 ROS 发行版列表。"""
        code, out, _ = self._run("ls -1 /opt/ros 2>/dev/null || true", log=False)
        return sorted(d for d in (out or "").splitlines() if d.strip())

    def write(self, text):
        """写入 ~/.bashrc，写入前自动备份原文件。"""
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        self._run("cp ~/.bashrc ~/.bashrc.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true")
        code, out, err = self._run(
            f"echo {shlex.quote(b64)} | base64 -d > ~/.bashrc")
        if code != 0:
            raise RuntimeError((err or out).strip() or "写入 ~/.bashrc 失败")
        return True
