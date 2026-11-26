# -*- coding: utf-8 -*-
"""远程进程列表（任务管理器）。"""
from core.config import CMD_TIMEOUT


class ProcessManager:
    def __init__(self, ssh, logger=None):
        self.ssh = ssh
        self.logger = logger

    def _run(self, cmd, timeout=CMD_TIMEOUT):
        code, out, err = self.ssh.exec_command(cmd, timeout=timeout)
        if self.logger:
            self.logger.debug(f"SSH: {cmd}")
        return code, out, err

    def list_processes(self, top_n=100):
        """返回按 CPU 占用降序的进程列表（最多 top_n 个）。

        每项：pid / user / cpu(生命周期平均%) / mem(%) / rss_mb / cmd。
        """
        cmd = (f"ps -eo pid=,user=,pcpu=,pmem=,rss=,args= --sort=-pcpu "
               f"| head -n {int(top_n)}")
        code, out, err = self._run(cmd)
        if code not in (0, 141) or (code != 0 and not (out or "").strip()):
            raise RuntimeError((err or out).strip() or "获取进程列表失败")

        procs = []
        for line in (out or "").splitlines():
            line = line.rstrip()
            if not line:
                continue
            parts = line.split(None, 5)  # pid / user / cpu / mem / rss / cmd
            if len(parts) < 6:
                continue
            try:
                pid = int(parts[0])
                cpu = float(parts[2])
                mem = float(parts[3])
                rss_kb = int(parts[4])
            except ValueError:
                continue
            procs.append({
                "pid": pid,
                "user": parts[1],
                "cpu": cpu,
                "mem": mem,
                "rss_mb": round(rss_kb / 1024.0, 1),
                "cmd": parts[5],
            })
        return procs
