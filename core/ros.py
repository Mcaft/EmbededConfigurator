# -*- coding: utf-8 -*-
"""ROS 运行状态查询：节点 / 话题 / 服务（ROS1 与 ROS2）。"""
import shlex

from core.config import CMD_TIMEOUT

# ROS1 发行版集合（ROS1 使用 rosnode / rostopic / rosservice，其余按 ROS2 处理）
ROS1_DISTROS = {"noetic", "melodic", "kinetic", "indigo", "lunar", "jade"}


def is_ros1(distro):
    return (distro or "").strip().lower() in ROS1_DISTROS


class RosRuntime:
    def __init__(self, ssh, logger=None):
        self.ssh = ssh
        self.logger = logger

    def _run(self, cmd, timeout=CMD_TIMEOUT):
        code, out, err = self.ssh.exec_command(cmd, timeout=timeout)
        if self.logger:
            self.logger.debug(f"SSH: {cmd}")
        return code, out, err

    def _inner(self, distro, ws_paths, cmd):
        """拼出 bash -lc 内部的命令串：先 source 环境，再执行目标命令。"""
        parts = []
        if distro:
            parts.append(f"source /opt/ros/{distro}/setup.bash 2>/dev/null")
        for p in ws_paths or []:
            parts.append(f"source {p} 2>/dev/null")
        parts.append(cmd + " 2>&1")
        return " && ".join(parts)

    def run(self, distro, ws_paths, cmd, timeout=CMD_TIMEOUT):
        full = "bash -lc " + shlex.quote(self._inner(distro, ws_paths, cmd))
        code, out, err = self._run(full, timeout=timeout)
        return code, (out or "").strip(), err

    def list_nodes(self, distro, ws_paths):
        cmd = "rosnode list" if is_ros1(distro) else "ros2 node list"
        return self.run(distro, ws_paths, cmd)

    def list_topics(self, distro, ws_paths):
        cmd = "rostopic list -v" if is_ros1(distro) else "ros2 topic list -t"
        return self.run(distro, ws_paths, cmd)

    def list_services(self, distro, ws_paths):
        cmd = "rosservice list" if is_ros1(distro) else "ros2 service list"
        return self.run(distro, ws_paths, cmd)
