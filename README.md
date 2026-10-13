# Orin NX 地面站配置工具（HC-Configurator）

Windows 上位机，通过 USB RNDIS 与 Orin NX 建立网络连接，用 SSH 完成对 Orin NX 的
WiFi 配置、网络（IP）配置、热点（AP）配置与状态监控。目标设备无屏幕、无键盘，
所有操作均通过 SSH 远程完成。

## 技术栈

- 语言：Python 3.8+
- GUI：PyQt5
- SSH：paramiko
- 主题：深色 QSS（`ui/style.qss`）

## 目录结构

```
HC-Configurator/
├── main.py                 # 程序入口（加载 QSS 主题）
├── config.json             # 外部配置文件（登录账号/密码等）
├── core/
│   ├── config.py           # 常量与超时配置（仅兜底默认值）
│   ├── store.py            # 读写 config.json 持久化
│   ├── logger.py           # 文件 + UI 日志
│   ├── rndis.py            # RNDIS 网卡检测 / 本机 IP 配置
│   ├── ssh_client.py       # paramiko SSH 封装（含 keepalive 保活）
│   └── orin.py             # WiFi/IP/热点/状态 命令封装与解析
├── ui/
│   ├── style.qss           # 深色主题样式
│   ├── worker.py           # 线程池 + 信号
│   ├── connection_bar.py   # 顶部连接状态栏
│   ├── wifi_tab.py         # WiFi 客户端配置
│   ├── ip_tab.py           # Orin IP 配置
│   ├── hotspot_tab.py      # 热点配置
│   ├── status_tab.py       # 状态显示
│   └── main_window.py      # 主窗口
├── requirements.txt
└── run.bat
```

## 安装与运行

1. 安装 Python 3.8+（勾选 “Add to PATH”）。
2. 安装依赖：

   ```bat
   pip install -r requirements.txt
   ```

3. 运行：

   ```bat
   python main.py
   ```

   或直接双击 `run.bat`。

> 配置本机静态 IP（192.168.55.100）需要管理员权限：非管理员运行时，程序会通过 UAC
> 弹窗请求提权；也可直接「以管理员身份运行」。

## 登录账号 / 密码（写在外部 config.json）

SSH 登录的账号、密码**不写在代码里**，而是放在程序目录下的外部文件 `config.json` 中，
用任意文本编辑器打开即可修改：

```json
{
  "ssh_host": "192.168.55.1",
  "ssh_port": 22,
  "ssh_username": "nvidia",
  "ssh_password": "nvidia",
  "last_wifi_ssid": "",
  "last_wifi_password": "",
  "last_hotspot_ssid": "HC-Hotspot",
  "last_hotspot_password": "",
  "last_hotspot_autoconnect": true
}
```

- `ssh_host` / `ssh_port` / `ssh_username` / `ssh_password`：SSH 登录参数（sudo 命令也复用
  `ssh_password` 作为 sudo 密码）。
- 其余字段是「最近使用的 WiFi / 热点参数」，由程序自动保存，无需手动维护。
- 修改后重启程序生效；也可以在程序内的「设置」按钮里修改（同样写回此文件）。

## 使用说明

1. 用 USB 数据线连接 Orin NX 的 Device 模式 Type-C 口与上位机。
2. 启动程序，程序会自动检测 RNDIS 网卡；若本机 IP 不是 `192.168.55.1` 同网段，按提示配置。
3. 点击「连接」通过 SSH 登录 Orin NX（账号密码取自 `config.json`）。
4. 各功能页：
   - **WiFi 配置**：扫描可用 WiFi，双击列表项回填，输入密码后连接，成功后显示 WiFi IP。
   - **IP 配置**：选择要配置的连接，切换静态 IP / DHCP 并应用。
   - **热点配置**：启用/禁用热点、设置 SSID / 密码（≥8 位）/ 开机自启动。
   - **状态显示**：IP、WiFi 状态、CPU、内存、温度、磁盘、运行时间，默认每 4 秒自动刷新。

## 关键说明

- **保活**：SSH 连接启用了 keepalive（10s），避免 RNDIS / sshd 空闲或链路抖动导致的被动断开。
- **CPU 统计**：通过两次采样 `/proc/stat` 计算占用率，不依赖 `top`，避免无 TTY 环境卡住。
- **sudo**：nmcli 修改连接需 root 权限，程序用 `echo <密码> | sudo -S -p '' <cmd>`
  自动处理密码输入（使用 `config.json` 中的 `ssh_password` 作为 sudo 密码）。
- **单网卡角色**：同一张无线网卡通常不能同时做 STA（连 WiFi）与 AP（开热点），
  开启热点前请先断开 WiFi 客户端连接。
- **首次启动限制**：若 Orin NX 未完成 OOBE（初始用户创建），SSH 不可用，需先通过串口完成初始化。
- 日志保存在程序目录下 `hc_configurator.log`，最近使用的参数保存在 `config.json`。
