# -*- coding: utf-8 -*-
"""全局配置常量。"""
import os
import sys

APP_NAME = "EmbededConfigurator"
APP_VERSION = "1.1.0"

# ---- Orin NX 连接参数 ----
ORIN_IP = "192.168.55.1"       # L4T RNDIS 默认网关地址
ORIN_SSH_PORT = 22
ORIN_USERNAME = "nvidia"
ORIN_PASSWORD = "nvidia"

# ---- 上位机本机参数 ----
HOST_IP = "192.168.55.100"     # 上位机静态 IP（与 Orin 同网段）
HOST_NETMASK = "255.255.255.0"

# ---- 超时（秒）----
SSH_CONNECT_TIMEOUT = 10
CMD_TIMEOUT = 30
WIFI_CMD_TIMEOUT = 60

# ---- 状态轮询（毫秒）----
STATUS_POLL_INTERVAL_MS = 4000   # 3~5 秒

# ---- 热点 ----
HOTSPOT_CONNECTION_NAME = "HC-Hotspot"
HOTSPOT_DEFAULT_IP = "10.42.0.1"

# ---- 连接方式 ----
MODE_RNDIS = "rndis"   # USB RNDIS 连接
MODE_LAN = "lan"       # 局域网连接


def app_dir():
    """应用根目录（源码运行 / PyInstaller 打包运行均可）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(rel):
    """返回资源文件真实路径，兼容 PyInstaller（_MEIPASS）与源码运行。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    return os.path.join(app_dir(), rel)


CONFIG_FILE = os.path.join(app_dir(), "config.json")
LOG_FILE = os.path.join(app_dir(), "embededconfigurator.log")
