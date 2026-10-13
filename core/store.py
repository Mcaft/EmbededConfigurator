# -*- coding: utf-8 -*-
"""配置持久化（保存最近使用的 WiFi / IP / 热点参数）。"""
import json

from core.config import (
    CONFIG_FILE,
    ORIN_IP,
    ORIN_PASSWORD,
    ORIN_SSH_PORT,
    ORIN_USERNAME,
)

# 登录凭据等优先从外部 config.json 读取；以下仅为 config.json 缺失时的兜底默认值。
DEFAULT_CONFIG = {
    "ssh_host": ORIN_IP,
    "ssh_port": ORIN_SSH_PORT,
    "ssh_username": ORIN_USERNAME,
    "ssh_password": ORIN_PASSWORD,
    "last_wifi_ssid": "",
    "last_wifi_password": "",
    "last_hotspot_ssid": "HC-Hotspot",
    "last_hotspot_password": "",
    "last_hotspot_autoconnect": True,
}


class Store:
    def __init__(self, path=CONFIG_FILE):
        self.path = path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
