# -*- coding: utf-8 -*-
"""远程 systemd 服务管理（列表 / 启动 / 停止 / 重启 / 启用 / 禁用）。"""
import shlex

from core.config import CMD_TIMEOUT


class ServiceManager:
    def __init__(self, ssh, logger=None):
        self.ssh = ssh
        self.logger = logger

    def _run(self, cmd, timeout=CMD_TIMEOUT, use_sudo=False):
        code, out, err = self.ssh.exec_command(cmd, timeout=timeout, use_sudo=use_sudo)
        if self.logger:
            self.logger.debug(f"SSH: {cmd}")
        return code, out, err

    def list_units(self, filter_text=""):
        cmd = ("systemctl list-units --type=service --all --no-legend --no-pager "
               "--plain")
        if filter_text:
            cmd += " | grep -i " + shlex.quote(filter_text)
        code, out, err = self._run(cmd)
        if code not in (0, 1):  # grep 无匹配时返回 1，属正常
            raise RuntimeError((err or out).strip() or "获取服务列表失败")
        units = []
        for line in (out or "").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 4)  # unit / load / active / sub / description
            if len(parts) < 4:
                continue
            units.append({
                "unit": parts[0],
                "load": parts[1],
                "active": parts[2],
                "sub": parts[3],
                "description": parts[4] if len(parts) > 4 else "",
            })
        return units

    def action(self, unit, action, use_sudo=True):
        """对指定服务执行 start/stop/restart/enable/disable。"""
        cmd = f"systemctl {action} {shlex.quote(unit)}"
        code, out, err = self._run(cmd, use_sudo=use_sudo)
        if code != 0:
            raise RuntimeError((err or out).strip() or f"{action} {unit} 失败")
        return (out or "").strip() or f"{action} {unit} 成功"
