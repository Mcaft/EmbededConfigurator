# -*- coding: utf-8 -*-
"""远程时钟同步（chrony / NTP / systemd-timesyncd）与系统时间读取。"""
import shlex

from core.config import CMD_TIMEOUT


class TimeSyncClient:
    def __init__(self, ssh, logger=None):
        self.ssh = ssh
        self.logger = logger

    def _run(self, cmd, timeout=CMD_TIMEOUT, use_sudo=False, log=True):
        code, out, err = self.ssh.exec_command(cmd, timeout=timeout, use_sudo=use_sudo)
        if log and self.logger:
            self.logger.debug(f"SSH: {cmd}")
        return code, out, err

    # ---------------- 时间读取 ----------------
    def read_remote_time(self):
        """读取远端 Unix 时间戳（秒，含小数）。失败抛 RuntimeError。"""
        code, out, err = self._run("date +%s.%N", log=False)
        if code != 0 or not (out or "").strip():
            raise RuntimeError((err or out).strip() or "读取远端时间失败")
        try:
            return float(out.strip())
        except ValueError:
            raise RuntimeError("解析远端时间失败")

    # ---------------- timedatectl ----------------
    def get_timedatectl(self):
        code, out, err = self._run("timedatectl")
        if code != 0:
            raise RuntimeError((err or out).strip() or "timedatectl 不可用")
        return self._kv(out)

    @staticmethod
    def _kv(text):
        """把形如 'Key : value' 的多行文本解析为 dict。"""
        d = {}
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
        return d

    # ---------------- 后端检测 ----------------
    def detect_backend(self):
        """返回 (service_name, active)。未检测到返回 (None, False)。"""
        for svc in ("chronyd", "chrony", "systemd-timesyncd", "ntpd"):
            code, out, _ = self._run(
                f"systemctl is-active {svc} 2>/dev/null || true", log=False)
            state = (out or "").strip()
            if state == "active":
                return svc, True
            if code == 0 and state:
                return svc, False
        return None, False

    @staticmethod
    def is_chrony(service):
        return (service or "").startswith("chrony")

    # ---------------- chrony ----------------
    def get_chrony_tracking(self):
        code, out, _ = self._run("chronyc tracking 2>/dev/null || true", log=False)
        if code != 0 or not (out or "").strip():
            return None
        return self._kv(out)

    def get_chrony_sources(self):
        code, out, _ = self._run("chronyc sources -v 2>/dev/null || true", log=False)
        if code != 0:
            return None
        return out.strip() or None

    # ---------------- 操作 ----------------
    def enable_ntp(self):
        code, out, err = self._run("timedatectl set-ntp true", use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "启用 NTP 失败")
        return (out or "").strip() or "NTP 已启用"

    def disable_ntp(self):
        code, out, err = self._run("timedatectl set-ntp false", use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "禁用 NTP 失败")
        return (out or "").strip() or "NTP 已禁用"

    def resync(self, service=""):
        """立即重新同步。chrony 用 makestep，其余重启 systemd-timesyncd/chronyd。"""
        if self.is_chrony(service):
            code, out, err = self._run("chronyc makestep 2>&1", use_sudo=False)
            if code != 0:
                code, out, err = self._run("chronyc makestep 2>&1", use_sudo=True)
            if code != 0:
                raise RuntimeError((err or out).strip() or "makestep 失败")
            return (out or "").strip() or "已请求立即校时（makestep）"
        code, out, err = self._run(
            "systemctl restart systemd-timesyncd 2>/dev/null || "
            "systemctl restart chronyd 2>/dev/null || true",
            use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "重新同步失败")
        return (out or "").strip() or "已请求重新同步"

    def add_chrony_server(self, addr):
        """向 /etc/chrony/chrony.conf 追加 server 行并重启 chrony。"""
        addr = (addr or "").strip()
        if not addr:
            raise RuntimeError("请填写 NTP 服务器地址。")
        line = f"server {addr} iburst"
        add = (f"grep -q {shlex.quote('^server ' + addr)} "
               f"/etc/chrony/chrony.conf 2>/dev/null || "
               f"echo {shlex.quote(line)} >> /etc/chrony/chrony.conf")
        code, out, err = self._run(add, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "写入 chrony.conf 失败")
        code, out, err = self._run(
            "systemctl restart chronyd 2>/dev/null || "
            "systemctl restart chrony 2>/dev/null || true",
            use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "重启 chrony 失败")
        return f"已添加服务器 {addr} 并重启 chrony"
