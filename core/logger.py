# -*- coding: utf-8 -*-
"""文件 + UI 回调日志。"""
import datetime
import threading

from core.config import LOG_FILE


class Logger:
    def __init__(self, path=LOG_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._listeners = []

    def add_listener(self, fn):
        """fn(line) 会在每次写日志时被调用（可能在后台线程）。"""
        self._listeners.append(fn)

    def _write(self, level, msg):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        with self._lock:
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass
        for fn in list(self._listeners):
            try:
                fn(line)
            except Exception:
                pass
        return line

    def info(self, msg):
        return self._write("INFO", msg)

    def warn(self, msg):
        return self._write("WARN", msg)

    def error(self, msg):
        return self._write("ERROR", msg)

    def debug(self, msg):
        return self._write("DEBUG", msg)
