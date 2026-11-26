# -*- coding: utf-8 -*-
"""配置持久化：板卡连接配置 + 最近使用的 WiFi / 热点参数。"""
import json

from core.config import (
    CONFIG_FILE,
    MODE_LAN,
    MODE_RNDIS,
    ORIN_IP,
    ORIN_PASSWORD,
    ORIN_SSH_PORT,
    ORIN_USERNAME,
)

DEFAULT_CONFIG = {
    "active_board": "",
    "boards": [],
    "last_wifi_ssid": "",
    "last_wifi_password": "",
    "last_hotspot_ssid": "HC-Hotspot",
    "last_hotspot_password": "",
    "last_hotspot_autoconnect": True,
    "ui_scale": 1.0,
}


def _board(name, mode, host, port, username, password):
    return {
        "name": name,
        "mode": mode,
        "ssh_host": host,
        "ssh_port": port,
        "ssh_username": username,
        "ssh_password": password,
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
        self._migrate()

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _migrate(self):
        boards = self.data.get("boards")
        if isinstance(boards, list) and boards:
            active = self.data.get("active_board")
            if not active or not any(b.get("name") == active for b in boards):
                self.data["active_board"] = boards[0]["name"]
            return

        # 旧版扁平配置（ssh_host/ssh_username/...）迁移为板卡列表
        legacy_host = self.data.get("ssh_host")
        if legacy_host:
            mode = MODE_RNDIS if legacy_host == ORIN_IP else MODE_LAN
            port = self.data.get("ssh_port", ORIN_SSH_PORT)
            user = self.data.get("ssh_username", ORIN_USERNAME)
            pwd = self.data.get("ssh_password", "")
            legacy = _board("Orin NX", mode, legacy_host, port, user, pwd)
            if mode == MODE_RNDIS:
                other = _board("Orin NX (局域网)", MODE_LAN, "", port, user, pwd)
            else:
                other = _board("Orin NX (RNDIS)", MODE_RNDIS, ORIN_IP, port, user, pwd)
            boards = [legacy, other]
        else:
            boards = [
                _board("Orin NX (RNDIS)", MODE_RNDIS, ORIN_IP, ORIN_SSH_PORT,
                       ORIN_USERNAME, ORIN_PASSWORD),
                _board("Orin NX (局域网)", MODE_LAN, "", ORIN_SSH_PORT,
                       ORIN_USERNAME, ORIN_PASSWORD),
            ]
        self.data["boards"] = boards
        self.data["active_board"] = boards[0]["name"]
        # 清理旧版扁平键，避免冗余残留
        for key in ("ssh_host", "ssh_port", "ssh_username", "ssh_password"):
            self.data.pop(key, None)
        # 一次性迁移：立即写回新格式，避免下次启动重复迁移
        self.save()

    # ---- 通用键值（last_wifi / last_hotspot）----
    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    # ---- 板卡 ----
    def get_boards(self):
        return list(self.data.get("boards", []))

    def set_boards(self, boards):
        self.data["boards"] = boards
        self.save()

    def get_active_board_name(self):
        return self.data.get("active_board", "")

    def get_active_board(self):
        name = self.get_active_board_name()
        for b in self.get_boards():
            if b.get("name") == name:
                return b
        boards = self.get_boards()
        return boards[0] if boards else None

    def set_active_board(self, name):
        self.data["active_board"] = name
        self.save()
