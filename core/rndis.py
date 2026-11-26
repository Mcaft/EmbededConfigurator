# -*- coding: utf-8 -*-
"""本机 USB 网卡（RNDIS / CDC-ECM / CDC-NCM）检测与 IP 配置。

Windows 通过 PowerShell + netsh 实现；Linux 通过 /sys + ip 实现。
"""
import csv
import ctypes
import io
import os
import re
import shutil
import subprocess
import sys

from core.config import HOST_IP, HOST_NETMASK

IS_WINDOWS = sys.platform.startswith("win")

_LINUX_USB_NET_DRIVERS = ("rndis_host", "cdc_ether", "cdc_ncm")
_IFNAME_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


# ==================== 通用入口 ====================
def is_admin():
    """当前进程是否具有管理员/root 权限。"""
    if IS_WINDOWS:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def detect_rndis_adapter():
    """检测 USB 网卡，返回 dict(name/description/status) 或 None。"""
    if IS_WINDOWS:
        return _win_detect()
    return _linux_detect()


def get_adapter_ip(name):
    """返回指定网卡当前 IPv4 地址，未配置返回空串。"""
    if IS_WINDOWS:
        return _win_get_ip(name)
    return _linux_get_ip(name)


def configure_host_ip(name, ip=HOST_IP, mask=HOST_NETMASK):
    """把本机 USB 网卡配置为静态 IP。

    返回 (ok, message)。Windows 非管理员时通过 UAC 提权，
    Linux 非 root 时通过 pkexec（polkit）提权。
    """
    if IS_WINDOWS:
        return _win_configure(name, ip, mask)
    return _linux_configure(name, ip, mask)


# ==================== Windows ====================
def _run_powershell(args, timeout=15):
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           errors="replace")
        return p.stdout.strip(), p.stderr.strip(), p.returncode
    except Exception as e:
        return "", str(e), -1


def _win_detect():
    ps = (
        "Get-NetAdapter | Where-Object { "
        "$_.InterfaceDescription -like '*Remote NDIS*' -or "
        "$_.InterfaceDescription -like '*RNDIS*' } | "
        "Select-Object Name,InterfaceDescription,Status | "
        "ConvertTo-Csv -NoTypeInformation"
    )
    out, _, code = _run_powershell(ps)
    if code != 0:
        return None
    rows = list(csv.DictReader(io.StringIO(out)))
    if not rows:
        return None
    r = rows[0]
    return {
        "name": (r.get("Name") or "").strip(),
        "description": (r.get("InterfaceDescription") or "").strip(),
        "status": (r.get("Status") or "").strip(),
    }


def _win_get_ip(name):
    ps = (
        f"Get-NetIPAddress -InterfaceAlias '{name}' -AddressFamily IPv4 | "
        "Select-Object -First 1 -ExpandProperty IPAddress"
    )
    out, _, code = _run_powershell(ps)
    if code != 0:
        return ""
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return lines[0] if lines else ""


def _win_configure(name, ip, mask):
    netsh_args = f'interface ipv4 set address name="{name}" static {ip} {mask}'
    if is_admin():
        try:
            p = subprocess.run(
                ["netsh"] + netsh_args.split(),
                capture_output=True, text=True, errors="replace", timeout=30,
            )
        except Exception as e:
            return False, f"执行 netsh 失败：{e}"
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0:
            return True, f"本机 IP 已配置为 {ip}/{mask}"
        return False, out.strip() or "配置失败"

    # 非管理员：通过 UAC 提权运行 netsh（异步执行，无法捕获输出）
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "netsh", netsh_args, None, 1)
    except Exception as e:
        return False, f"提权失败：{e}"
    if ret > 32:
        return True, "已请求管理员权限，请在 UAC 弹窗中点击“是”，稍后自动生效。"
    return False, f"提权失败（错误码 {ret}）。请以管理员身份运行本程序后重试。"


# ==================== Linux ====================
def _linux_run(cmd, timeout=15):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           errors="replace")
        return p.stdout.strip(), p.stderr.strip(), p.returncode
    except Exception as e:
        return "", str(e), -1


def _linux_driver(ifname):
    """返回网卡绑定的驱动名，如 rndis_host / cdc_ether。"""
    try:
        return os.path.basename(
            os.path.realpath(f"/sys/class/net/{ifname}/device/driver"))
    except OSError:
        return ""


def _linux_operstate(ifname):
    try:
        with open(f"/sys/class/net/{ifname}/operstate", "r", encoding="ascii") as f:
            return f.read().strip()
    except OSError:
        return ""


def _linux_detect():
    try:
        names = sorted(os.listdir("/sys/class/net"))
    except OSError:
        return None

    candidates = []
    for name in names:
        if name == "lo":
            continue
        driver = _linux_driver(name)
        if driver in _LINUX_USB_NET_DRIVERS or name.startswith(("usb", "enx")):
            candidates.append(name)
    if not candidates:
        return None

    def _rank(ifname):
        driver = _linux_driver(ifname)
        if driver == "rndis_host":
            return 0
        if ifname.startswith("usb"):
            return 1
        if driver in _LINUX_USB_NET_DRIVERS:
            return 2
        return 3

    name = sorted(candidates, key=_rank)[0]
    state = _linux_operstate(name)
    return {
        "name": name,
        "description": _linux_driver(name) or "usb-net",
        "status": state.capitalize() if state else "Unknown",
    }


def _linux_get_ip(name):
    out, _, code = _linux_run(["ip", "-4", "-o", "addr", "show", "dev", name])
    if code != 0:
        return ""
    m = re.search(r"\binet (\d{1,3}(?:\.\d{1,3}){3})", out)
    return m.group(1) if m else ""


def _mask_to_prefix(mask):
    try:
        parts = [int(p) for p in mask.split(".")]
        if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
            return 24
        return sum(bin(p).count("1") for p in parts)
    except (ValueError, AttributeError):
        return 24


def _linux_configure(name, ip, mask):
    if not _IFNAME_RE.match(name or ""):
        return False, f"网卡名不合法：{name!r}"

    prefix = _mask_to_prefix(mask)
    script = (
        f"ip addr flush dev {name}; "
        f"ip addr add {ip}/{prefix} dev {name}; "
        f"ip link set dev {name} up"
    )

    if is_admin():
        out, err, code = _linux_run(["sh", "-c", script], timeout=30)
        if code == 0:
            return True, f"本机 IP 已配置为 {ip}/{prefix}"
        return False, (err or out).strip() or "配置失败"

    if shutil.which("pkexec"):
        out, err, code = _linux_run(["pkexec", "sh", "-c", script], timeout=120)
        if code == 0:
            return True, f"本机 IP 已配置为 {ip}/{prefix}"
        msg = (err or out).strip()
        return False, msg or "提权被取消，或 polkit 授权失败。"

    return False, "需要 root 权限。请用 sudo 运行本程序，或安装 pkexec（polkit）。"
