# -*- coding: utf-8 -*-
"""对 Orin NX 的高层操作封装（依赖已连接的 SSHClient）。"""
import re
import shlex

from core.config import (
    CMD_TIMEOUT,
    HOTSPOT_CONNECTION_NAME,
    WIFI_CMD_TIMEOUT,
)


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return -1


def mask_to_prefix(mask):
    """把子网掩码转换为前缀长度，非法返回 None。"""
    try:
        parts = [int(x) for x in mask.split(".")]
    except (ValueError, AttributeError):
        return None
    if len(parts) != 4 or any(not 0 <= p <= 255 for p in parts):
        return None
    binary = "".join(f"{p:08b}" for p in parts)
    if "01" in binary:  # 非连续掩码
        return None
    return binary.count("1")


class OrinClient:
    def __init__(self, ssh, logger=None):
        self.ssh = ssh
        self.logger = logger

    def _run(self, cmd, timeout=CMD_TIMEOUT, use_sudo=False, log=True):
        code, out, err = self.ssh.exec_command(cmd, timeout=timeout, use_sudo=use_sudo)
        if log and self.logger:
            self.logger.debug(f"SSH: {cmd}")
            if code is not None:
                detail = (out + err).strip().replace("\n", " ")
                if detail:
                    self.logger.debug(f"  -> [{code}] {detail[:300]}")
        return code, out, err

    # ---------------- WiFi 客户端 ----------------
    def scan_wifi(self):
        self._run("nmcli device wifi rescan", timeout=CMD_TIMEOUT, use_sudo=True)
        code, out, err = self._run(
            "nmcli -t -f SSID,SIGNAL,SECURITY,IN-USE device wifi list",
            timeout=CMD_TIMEOUT, use_sudo=False)
        if code != 0:
            # 部分环境列出也需要权限
            code, out, err = self._run(
                "nmcli -t -f SSID,SIGNAL,SECURITY,IN-USE device wifi list",
                timeout=CMD_TIMEOUT, use_sudo=True)
        if code is None:
            raise RuntimeError(err or "扫描 WiFi 失败")
        return self._parse_wifi_list(out)

    @staticmethod
    def _parse_wifi_list(out):
        networks = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            ssid = (parts[0] if parts else "").replace("\\:", ":").replace("\\\\", "\\")
            signal = parts[1] if len(parts) > 1 else ""
            security = parts[2] if len(parts) > 2 else ""
            in_use = (parts[3] if len(parts) > 3 else "").strip() == "*"
            if not ssid:
                continue
            networks.append({
                "ssid": ssid,
                "signal": signal,
                "security": security,
                "in_use": in_use,
            })
        # 同名 SSID 保留信号最强
        best = {}
        for n in networks:
            key = n["ssid"]
            if key not in best or _to_int(n["signal"]) > _to_int(best[key]["signal"]):
                best[key] = n
        return sorted(best.values(), key=lambda x: _to_int(x["signal"]), reverse=True)

    def connect_wifi(self, ssid, password):
        self._run("nmcli radio wifi on", timeout=CMD_TIMEOUT, use_sudo=True)
        if password:
            cmd = (f"nmcli device wifi connect {shlex.quote(ssid)} "
                   f"password {shlex.quote(password)}")
        else:
            cmd = f"nmcli device wifi connect {shlex.quote(ssid)}"
        code, out, err = self._run(cmd, timeout=WIFI_CMD_TIMEOUT, use_sudo=True)
        combined = (out or "") + "\n" + (err or "")
        if code == 0 and "successfully activated" in combined:
            return {"ip": self.get_wlan_ip(), "raw": combined.strip()}
        raise RuntimeError(self._map_wifi_error(combined))

    @staticmethod
    def _map_wifi_error(text):
        t = (text or "").lower()
        if ("secrets" in t and "required" in t) or "invalid password" in t or "no valid secrets" in t:
            return "密码错误，请重新输入。"
        if "no network with ssid" in t or "not found" in t:
            return "未找到该 SSID，请检查名称或刷新扫描列表。"
        if "timeout" in t or "timed out" in t:
            return "连接超时，请重试。"
        if "already exists" in t:
            return "同名连接已存在，请先删除旧连接后重试。"
        return (text or "").strip() or "连接失败，未知错误。"

    def get_wlan_ip(self):
        code, out, _ = self._run("ip -4 -o addr show wlan0", timeout=CMD_TIMEOUT, log=False)
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", out)
        if m:
            return m.group(1)
        code, out, _ = self._run("hostname -I", timeout=CMD_TIMEOUT, log=False)
        ips = (out or "").strip().split()
        return ips[0] if ips else ""

    # ---------------- 接口与连接枚举 ----------------
    def get_interfaces(self):
        code, out, err = self._run(
            "nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status", timeout=CMD_TIMEOUT)
        if code is None:
            raise RuntimeError(err or "获取接口失败")
        devices = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            devices.append({
                "device": parts[0],
                "type": parts[1] if len(parts) > 1 else "",
                "state": parts[2] if len(parts) > 2 else "",
                "connection": parts[3] if len(parts) > 3 else "",
            })
        return devices

    def get_connections(self):
        code, out, err = self._run(
            "nmcli -t -f NAME,TYPE,DEVICE connection show", timeout=CMD_TIMEOUT)
        if code is None:
            raise RuntimeError(err or "获取连接失败")
        conns = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            conns.append({
                "name": parts[0],
                "type": parts[1] if len(parts) > 1 else "",
                "device": parts[2] if len(parts) > 2 else "",
            })
        return conns

    def get_saved_wifi_connections(self):
        """返回已保存的 WiFi（802-11-wireless）连接列表。"""
        code, out, err = self._run(
            "nmcli -t -f NAME,TYPE,DEVICE connection show", timeout=CMD_TIMEOUT)
        if code is None:
            raise RuntimeError(err or "获取已保存 WiFi 连接失败")
        conns = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) < 2 or parts[1] != "802-11-wireless":
                continue
            conns.append({
                "name": parts[0],
                "device": parts[2] if len(parts) > 2 else "",
            })
        return conns

    def forget_wifi(self, connection_name):
        """删除（忘记）指定名称的 WiFi 连接，返回 True。"""
        # 若连接正在使用，先断开再删除
        self._run(f"nmcli connection down {shlex.quote(connection_name)}",
                  timeout=CMD_TIMEOUT, use_sudo=True)
        code, out, err = self._run(
            f"nmcli connection delete {shlex.quote(connection_name)}",
            timeout=CMD_TIMEOUT, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "忘记 WiFi 失败")
        return True

    # ---------------- IP 配置 ----------------
    def set_static_ip(self, connection_name, ip, prefix, gateway="", dns=""):
        parts = ["ipv4.method manual", f"ipv4.addresses {ip}/{prefix}"]
        parts.append(f"ipv4.gateway {gateway}" if gateway else 'ipv4.gateway ""')
        parts.append(f"ipv4.dns {dns}" if dns else "ipv4.ignore-auto-dns yes")
        modify = f"nmcli connection modify {shlex.quote(connection_name)} " + " ".join(parts)
        code, out, err = self._run(modify, timeout=CMD_TIMEOUT, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "修改连接失败")
        code, out, err = self._run(
            f"nmcli connection up {shlex.quote(connection_name)}",
            timeout=WIFI_CMD_TIMEOUT, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "应用连接失败")
        return self.get_ip_addresses()

    def set_dhcp(self, connection_name):
        modify = f"nmcli connection modify {shlex.quote(connection_name)} ipv4.method auto"
        code, out, err = self._run(modify, timeout=CMD_TIMEOUT, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "修改连接失败")
        code, out, err = self._run(
            f"nmcli connection up {shlex.quote(connection_name)}",
            timeout=WIFI_CMD_TIMEOUT, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "应用连接失败")
        return self.get_ip_addresses()

    def get_ip_addresses(self):
        code, out, err = self._run("ip -4 -o addr show", timeout=CMD_TIMEOUT, log=False)
        ips = []
        for line in out.splitlines():
            m = re.search(r"^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", line)
            if m:
                ips.append({"interface": m.group(1), "ip": m.group(2), "prefix": m.group(3)})
        return ips

    # ---------------- 热点（AP）----------------
    def _connection_exists(self, name):
        code, out, _ = self._run(
            f"nmcli -t -f NAME connection show {shlex.quote(name)}", timeout=CMD_TIMEOUT)
        return code == 0 and name in out

    def configure_hotspot(self, enable, ssid, password, autoconnect, ifname="wlan0"):
        con = HOTSPOT_CONNECTION_NAME
        if self._connection_exists(con):
            for m in (
                f"nmcli connection modify {shlex.quote(con)} 802-11-wireless.ssid {shlex.quote(ssid)}",
                f"nmcli connection modify {shlex.quote(con)} 802-11-wireless-security.psk {shlex.quote(password)}",
            ):
                code, out, err = self._run(m, timeout=CMD_TIMEOUT, use_sudo=True)
                if code != 0:
                    raise RuntimeError((err or out).strip() or "更新热点参数失败")
        else:
            cmd = (f"nmcli device wifi hotspot ifname {shlex.quote(ifname)} "
                   f"con-name {shlex.quote(con)} ssid {shlex.quote(ssid)} "
                   f"password {shlex.quote(password)}")
            code, out, err = self._run(cmd, timeout=WIFI_CMD_TIMEOUT, use_sudo=True)
            if code != 0:
                raise RuntimeError((err or out).strip() or "创建热点失败")

        val = "yes" if autoconnect else "no"
        code, out, err = self._run(
            f"nmcli connection modify {shlex.quote(con)} connection.autoconnect {val}",
            timeout=CMD_TIMEOUT, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or "设置自启动失败")

        action = f"nmcli connection {'up' if enable else 'down'} {shlex.quote(con)}"
        code, out, err = self._run(action, timeout=WIFI_CMD_TIMEOUT, use_sudo=True)
        if code != 0:
            raise RuntimeError((err or out).strip() or ("启用热点失败" if enable else "禁用热点失败"))
        return True

    # ---------------- 状态 ----------------
    def get_status(self):
        script = (
            'echo "===IP==="; ip -4 -o addr show; '
            'echo "===WIFI==="; nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status; '
            'echo "===CPU==="; grep "^cpu " /proc/stat; sleep 0.3; grep "^cpu " /proc/stat; '
            'echo "===MEM==="; free -m; '
            'echo "===TEMP==="; '
            'for d in /sys/devices/virtual/thermal/thermal_zone*; do '
            't=$(cat "$d/type" 2>/dev/null); v=$(cat "$d/temp" 2>/dev/null); '
            'echo "$t:$v"; done; '
            'echo "===DISK==="; df -h /; '
            'echo "===UPTIME==="; uptime; '
            'echo "===GPU==="; timeout 2 tegrastats --interval 1000 2>/dev/null | tail -n 1'
        )
        code, out, err = self._run(script, timeout=CMD_TIMEOUT, log=False)
        if code is None and not out:
            raise RuntimeError(err or "获取状态失败")
        return self._parse_status(out)

    @staticmethod
    def _parse_status(out):
        status = {"ips": [], "wifi": [], "cpu": None, "memory": None,
                  "temperatures": [], "disk": None, "uptime": "", "gpu": None}
        sections = re.split(r"^===(\w+)===\s*$", out, flags=re.MULTILINE)
        for i in range(1, len(sections) - 1, 2):
            key = sections[i]
            content = sections[i + 1]
            if key == "IP":
                status["ips"] = OrinClient._parse_ips(content)
            elif key == "WIFI":
                status["wifi"] = OrinClient._parse_devices(content)
            elif key == "CPU":
                status["cpu"] = OrinClient._parse_cpu(content)
            elif key == "MEM":
                status["memory"] = OrinClient._parse_mem(content)
            elif key == "TEMP":
                status["temperatures"] = OrinClient._parse_temp(content)
            elif key == "DISK":
                status["disk"] = OrinClient._parse_disk(content)
            elif key == "UPTIME":
                status["uptime"] = content.strip()
            elif key == "GPU":
                status["gpu"] = OrinClient._parse_tegrastats(content)
        return status

    @staticmethod
    def _parse_ips(content):
        ips = []
        for line in content.splitlines():
            m = re.search(r"^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", line)
            if m:
                ips.append({"interface": m.group(1), "ip": m.group(2), "prefix": m.group(3)})
        return ips

    @staticmethod
    def _parse_devices(content):
        devices = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) < 2:
                continue
            devices.append({
                "device": parts[0],
                "type": parts[1],
                "state": parts[2] if len(parts) > 2 else "",
                "connection": parts[3] if len(parts) > 3 else "",
            })
        return devices

    @staticmethod
    def _parse_cpu(content):
        # 两次采样 /proc/stat 的 "cpu " 行，用差值计算占用率
        lines = [l for l in content.splitlines() if l.strip().startswith("cpu ")]
        if len(lines) < 2:
            return None

        def _vals(line):
            parts = line.split()[1:]
            vals = [int(x) for x in parts[:8]]
            vals += [0] * (8 - len(vals))
            return vals

        v1, v2 = _vals(lines[0]), _vals(lines[-1])
        dt = sum(v2) - sum(v1)
        if dt <= 0:
            return None
        idle = (v2[3]) - (v1[3])                              # idle
        iowait = (v2[4]) - (v1[4])                            # iowait
        user = (v2[0] + v2[1]) - (v1[0] + v1[1])              # user + nice
        sys_ = (v2[2] + v2[5] + v2[6]) - (v1[2] + v1[5] + v1[6])  # system+irq+softirq
        busy = dt - idle - iowait
        return {
            "user": round(user / dt * 100, 1),
            "system": round(sys_ / dt * 100, 1),
            "idle": round(idle / dt * 100, 1),
            "wait": round(iowait / dt * 100, 1),
            "usage": round(busy / dt * 100, 1),
        }

    @staticmethod
    def _parse_mem(content):
        for line in content.splitlines():
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) < 3:
                    continue
                total = int(parts[1])
                used = int(parts[2])
                avail = int(parts[6]) if len(parts) > 6 else total - used
                percent = round(used * 100.0 / total, 1) if total else 0.0
                return {"total_mb": total, "used_mb": used,
                        "available_mb": avail, "percent": percent}
        return None

    @staticmethod
    def _parse_temp(content):
        temps = []
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            name, val = line.split(":", 1)
            name = name.strip()
            try:
                mv = int(val.strip())
            except ValueError:
                continue
            temps.append({"name": name, "celsius": mv / 1000.0})
        return temps

    @staticmethod
    def _parse_disk(content):
        lines = [l for l in content.splitlines() if l.strip()]
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 6:
                return {"filesystem": parts[0], "size": parts[1], "used": parts[2],
                        "available": parts[3], "percent": parts[4]}
        return None

    @staticmethod
    def _parse_tegrastats(content):
        """解析 tegrastats 采样行，尽量容错地提取 GPU / EMC / 功耗 / 温度。

        不同 L4T 版本的输出格式差异较大，这里只按正则提取能识别的字段，
        提取不到的字段保持 None，由界面层兜底显示。
        """
        lines = [l for l in (content or "").splitlines() if l.strip()]
        if not lines:
            return None
        line = lines[-1]
        info = {"gpu": None, "emc": None, "power": None, "temp": None,
                "ram": None, "raw": line}

        m = re.search(r"GR3D_FREQ\s+(\d+)%", line)
        if m:
            info["gpu"] = int(m.group(1))
        m = re.search(r"EMC_FREQ\s+(\d+)%", line)
        if m:
            info["emc"] = int(m.group(1))
        m = re.search(r"RAM\s+(\d+)/(\d+)MB", line)
        if m:
            info["ram"] = f"{m.group(1)}/{m.group(2)} MB"

        # 功耗：取所有 mW 数值的最大值（覆盖 VDD_IN / POM_5V_IN 等不同命名）
        powers = [int(x) for x in re.findall(r"(\d+)mW", line)]
        if powers:
            info["power"] = max(powers)
        # 温度：匹配 AO@ / GPU@ / Tdiode@ / tj@ / PMIC@ 等常见采样点
        temps = [float(x) for x in re.findall(r"(?:AO|GPU|Tdiode|tj|PMIC)@([\d.]+)C", line)]
        if temps:
            info["temp"] = max(temps)
        return info
