
EmbededConfigurator（Orin NX 地面站配置工具）

1. 项目背景
   上位机（Windows 地面站）需要通过 USB RNDIS 与 Orin NX 建立网络连接，完成对 Orin NX 的 WiFi 配置、网络配置和状态监控。目标设备无屏幕、无键盘，所有操作必须通过 SSH 远程完成。
2. 连接方式
   项目	值
   物理连接	USB 数据线（连接 Orin NX 的 Device 模式 Type-C 口与上位机）
   Orin 端 IP	192.168.55.1（L4T RNDIS 默认网关地址）
   上位机 IP	192.168.55.100（静态配置，需与 Orin 同网段）
   子网掩码	255.255.255.0
   协议	SSH (TCP 22)
   默认用户名	nvidia
   默认密码	nvidia
   上位机需在启动时自动检测 RNDIS 网卡（Remote NDIS Compatible Device），并确保本机 IP 配置正确。若未识别，提示用户安装 RNDIS 驱动。
3. 功能需求
   3.1 WiFi 客户端配置
   目标：让 Orin NX 连接到用户指定的局域网 WiFi。

输入：

SSID（WiFi 名称）

密码

（可选）加密方式（默认 WPA2）

行为：

通过 SSH 在 Orin 上执行 nmcli radio wifi on 开启 WiFi。

执行 nmcli device wifi connect "<SSID></ssid>" password "<PASSWORD></password>" 连接目标 WiFi。

等待并解析返回结果，判断是否成功（检测 successfully activated）。

返回连接后的 WiFi IP 地址。

异常处理：

密码错误 → 提示重新输入。

SSID 未找到 → 提示用户检查名称或刷新扫描列表。

连接超时 → 重试或提示用户。

辅助功能：

扫描可用 WiFi 列表：nmcli device wifi list，将结果展示给用户选择。

3.2 Orin 自身 IP 配置
目标：配置 Orin NX 的静态 IP 或切换回 DHCP。

输入：

网络接口名（如 wlan0、eth0，应支持自动枚举）

模式：静态 IP / DHCP

若为静态 IP：IP 地址、子网掩码、网关、DNS

行为：

静态 IP：

text
nmcli connection modify "<连接名>" ipv4.method manual 
  ipv4.addresses <IP></ip>/<前缀> 
  ipv4.gateway <网关> 
  ipv4.dns <DNS></dns>
nmcli connection up "<连接名>"
DHCP：

text
nmcli connection modify "<连接名>" ipv4.method auto
nmcli connection up "<连接名>"
注意事项：

应允许用户选择对哪个连接（WiFi 或以太网）进行配置。

修改 IP 后需重新读取接口地址以确认生效。

3.3 热点（AP）配置
目标：让 Orin NX 创建 WiFi 热点，供其他设备连接。

输入：

是否启用热点（开关）

热点 SSID

热点密码（≥ 8 位）

是否开机自启动（开关）

行为：

创建/更新热点：

text
nmcli device wifi hotspot ifname <wlan0></wlan0> con-name <热点连接名> 
  ssid "<SSID></ssid>" password "<PASSWORD></password>"
启用/禁用热点：

text
nmcli connection up <热点连接名>
nmcli connection down <热点连接名>
设置自启动：

text
nmcli connection modify <热点连接名> connection.autoconnect yes
nmcli connection modify <热点连接名> connection.autoconnect no
约束：

若 WiFi 网卡同时要作为客户端连接和热点，需提示用户二选一（同一张网卡通常不能同时做 STA 和 AP，除非硬件支持）。

热点默认网关 IP 通常为 10.42.0.1，应显示给用户。

密码长度不足 8 位时应拒绝提交。

3.4 状态显示
目标：实时或按需展示 Orin NX 的关键运行状态。

状态项	SSH 命令	说明
IP 地址	ip -4 addr show 或 hostname -I	展示所有接口的 IPv4 地址
WiFi 连接状态	nmcli device status	显示 wlan0 是否已连接、连接的 SSID
CPU 占用	top -bn1 | grep "Cpu(s)" 或 cat /proc/stat	可解析出用户/系统/空闲占比
内存占用	free -m	已用/总量
温度	cat /sys/devices/virtual/thermal/thermal_zone*/temp	各热区温度（需除以 1000 得摄氏度）
磁盘占用	df -h /	根分区使用率
运行时间	uptime	系统负载与运行时长
刷新策略：

默认每 3–5 秒轮询一次。

提供手动刷新按钮。

连接断开时显示离线状态并自动重连。

温度说明：
Orin NX 有多个 thermal zone，通常：

thermal_zone0 ~ thermal_zone7 对应 CPU、GPU、SoC、CV 等不同区域。

应对每个 zone 读取 type 文件获得名称，再读取 temp 获得温度值。

4. 交互与 UI 需求（建议）
   区域	内容
   连接栏	显示 SSH 连接状态（已连接 / 未连接 / 连接中），Orin IP，重连按钮
   WiFi 配置区	SSID 输入框、密码输入框、扫描按钮、扫描结果列表、连接按钮
   IP 配置区	接口选择下拉框、静态/DHCP 切换、IP/掩码/网关/DNS 输入、应用按钮
   热点配置区	启用开关、SSID 输入、密码输入、自启动开关、应用按钮
   状态面板	IP、CPU、内存、温度（多 zone）、磁盘、运行时间，自动刷新
   所有操作应有明确的成功/失败提示，并记录日志。
5. 技术建议
   SSH 库：Python 用 paramiko，Node.js 用 ssh2，Go 用 golang.org/x/crypto/ssh。

命令执行：每条命令独立执行，避免交互式命令卡住。sudo 需处理密码输入（可用 echo <password></password> | sudo -S <cmd></cmd> 或配置免密 sudo）。

超时：SSH 连接超时建议 10s，命令执行超时 30s（WiFi 连接可放宽至 60s）。

错误解析：捕获 stderr 与退出码，将常见错误映射为友好提示。

持久化：可保存最近使用的 WiFi、IP 配置、热点参数，方便下次快速填写。

日志：记录所有 SSH 命令与返回，便于排查问题。

6. 关键约束与风险
   首次启动限制：若 Orin 未完成 OOBE（初始用户创建），SSH 不可用，需先通过串口完成初始化。

单 Device 口限制：Orin NX 同一时刻只有一个 USB 口工作于 Device 模式，RNDIS 仅在该口有效。

WiFi 网卡单角色：同一张无线网卡通常不能同时作为 STA（连 WiFi）和 AP（开热点），需明确用户场景。

sudo 权限：nmcli 修改连接需 root 权限，需确保 nvidia 用户可免密 sudo 或脚本能处理密码。

RNDIS 驱动：Windows 端需正确识别 RNDIS 设备，否则无法建立 192.168.55.x 网络。

7. 验收标准
   □ 上位机能自动检测 RNDIS 并建立到 192.168.55.1 的 SSH 连接。
   □ 能扫描并连接指定 WiFi，成功后显示获取到的 IP。
   □ 能对指定接口配置静态 IP 或 DHCP 并生效。
   □ 能启用/禁用热点，设置 SSID、密码、自启动。
   □ 状态面板能正确显示 IP、CPU、内存、温度、磁盘、运行时间。
   □ 所有操作有成功/失败反馈，异常有明确提示。
