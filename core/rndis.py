# -*- coding: utf-8 -*-
"""Windows 端 RNDIS 网卡检测与本机 IP 配置。"""
import csv
import ctypes
import io
import subprocess

from core.config import HOST_IP, HOST_NETMASK


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _run_powershell(args, timeout=15):
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           errors="replace")
        return p.stdout.strip(), p.stderr.strip(), p.returncode
    except Exception as e:
        return "", str(e), -1


def detect_rndis_adapter():
    """检测 RNDIS 网卡，返回 dict(name/description/status) 或 None。"""
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


def get_adapter_ip(name):
    """返回指定网卡当前 IPv4 地址，未配置返回空串。"""
    ps = (
        f"Get-NetIPAddress -InterfaceAlias '{name}' -AddressFamily IPv4 | "
        "Select-Object -First 1 -ExpandProperty IPAddress"
    )
    out, _, code = _run_powershell(ps)
    if code != 0:
        return ""
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return lines[0] if lines else ""


def configure_host_ip(name, ip=HOST_IP, mask=HOST_NETMASK):
    """把本机 RNDIS 网卡配置为静态 IP。需管理员权限，非管理员时尝试 UAC 提权。

    返回 (ok, message)。"""
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
