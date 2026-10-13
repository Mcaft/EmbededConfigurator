# -*- coding: utf-8 -*-
"""基于 paramiko 的 SSH 客户端封装。"""
import shlex
import socket
import threading

import paramiko

from core.config import CMD_TIMEOUT, SSH_CONNECT_TIMEOUT


class SSHClient:
    def __init__(self):
        self._client = None
        self._lock = threading.Lock()
        self.host = None
        self.port = 22
        self.username = ""
        self.password = ""

    def connect(self, host, port=22, username="nvidia", password="nvidia",
                timeout=SSH_CONNECT_TIMEOUT):
        self.disconnect()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host, port=port, username=username, password=password,
                timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
                allow_agent=False, look_for_keys=False,
            )
            # 保活：防止 RNDIS / sshd 空闲或链路抖动时被动断开
            transport = client.get_transport()
            if transport is not None:
                transport.set_keepalive(10)
        except Exception:
            client.close()
            raise
        self._client = client
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def disconnect(self):
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def is_connected(self):
        if self._client is None:
            return False
        try:
            t = self._client.get_transport()
            return t is not None and t.is_active()
        except Exception:
            return False

    def exec_command(self, cmd, timeout=CMD_TIMEOUT, use_sudo=False):
        """执行命令，返回 (exit_code, stdout, stderr)。失败时 exit_code 为 None。"""
        if not self.is_connected():
            return None, "", "SSH 未连接"
        run_cmd = cmd
        if use_sudo:
            run_cmd = f"echo {shlex.quote(self.password)} | sudo -S -p '' {cmd}"
        with self._lock:
            try:
                stdin, stdout, stderr = self._client.exec_command(run_cmd, timeout=timeout)
                # 先等命令结束（受通道超时约束），再读输出，避免 stdout/stderr 缓冲区
                # 互相占满导致死锁，也避免无 TTY 命令卡住时无限等待。
                stdout.channel.settimeout(timeout)
                code = stdout.channel.recv_exit_status()
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                return code, out, err
            except socket.timeout:
                return None, "", f"命令执行超时（{timeout}s）：{cmd}"
            except Exception as e:
                return None, "", str(e)
