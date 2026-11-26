# Orin NX 地面站配置工具（EmbededConfigurator）

Windows / Linux 上位机，通过 USB RNDIS 与 Orin NX 建立网络连接，用 SSH 完成对 Orin NX 的
WiFi 配置、网络（IP）配置、热点（AP）配置与状态监控。目标设备无屏幕、无键盘，
所有操作均通过 SSH 远程完成。

## 技术栈

- 语言：Python 3.8+
- GUI：PyQt5
- SSH：paramiko
- 主题：深色 QSS（`ui/style.qss`）

## 目录结构

```
EmbededConfigurator/
├── main.py                 # 程序入口（加载 QSS 主题 + 窗口图标）
├── config.json             # 外部配置文件（板卡连接配置等）
├── icon.svg                # 图标源文件
├── icon.ico                # 由 icon.svg 生成的多尺寸图标（Windows 程序/窗口图标）
├── icon.png                # 由 icon.svg 生成的 256px 图标（Linux 程序/窗口图标）
├── build.bat               # Windows 一键打包脚本
├── build.sh                # Linux 一键打包脚本
├── run.bat / run.sh        # 启动脚本
├── .github/workflows/      # GitHub Actions（Linux 包自动构建）
├── core/
│   ├── config.py           # 常量与超时配置（仅兜底默认值）
│   ├── store.py            # 读写 config.json 持久化（板卡列表等）
│   ├── logger.py           # 文件 + UI 日志
│   ├── scaling.py          # 界面缩放（QSS px 按比例重写）
│   ├── rndis.py            # USB 网卡检测 / 本机 IP 配置（Windows/Linux）
│   ├── ssh_client.py       # paramiko SSH 封装（含 keepalive 保活）
│   ├── orin.py             # WiFi/IP/热点/状态 命令封装与解析
│   ├── bashrc.py           # 远程 ~/.bashrc 读取/写入 + ROS 环境行解析
│   ├── ros.py              # ROS1/ROS2 节点/话题/服务 查询
│   ├── services.py         # 远程 systemd 服务管理
│   ├── timesync.py         # 时钟同步（chrony/NTP）与系统时间读取
│   └── processes.py        # 远程进程列表（任务管理器）
├── ui/
│   ├── style.qss           # 深色主题样式
│   ├── worker.py           # 线程池 + 信号
│   ├── plot_widget.py      # 自绘时间序列折线图（跳变标记）
│   ├── connection_bar.py   # 顶部连接状态栏（板卡选择 + 连接方式）
│   ├── board_dialog.py     # 板卡管理对话框（增删改板卡配置）
│   ├── wifi_tab.py         # WiFi 客户端配置
│   ├── ip_tab.py           # Orin IP 配置
│   ├── hotspot_tab.py      # 热点配置
│   ├── ros_env_tab.py      # ~/.bashrc ROS 环境配置
│   ├── ros_runtime_tab.py  # ROS 运行（节点/话题/服务）
│   ├── services_tab.py     # systemd 服务管理
│   ├── time_sync_tab.py    # 时钟同步 + 时间监测
│   ├── process_tab.py      # 任务管理器（进程）
│   ├── status_tab.py       # 状态显示
│   └── main_window.py      # 主窗口（左侧导航栏 + 页面栈）
└── requirements.txt
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

### Linux

```bash
# Debian / Ubuntu：Qt 运行所需的基础库
sudo apt install -y python3-pip libxcb-xinerama0 libxkbcommon-x11-0 libgl1
pip3 install -r requirements.txt
./run.sh          # 或 python3 main.py
```

- USB 网卡一般显示为 `usb0` 或 `enx*`，程序通过 `/sys/class/net/*/device/driver`
  识别 `rndis_host` / `cdc_ether` / `cdc_ncm`。
- 配置本机静态 IP 需要 root：以 root 运行，或安装 polkit（`pkexec`）后由程序弹出授权框。
- 若 NetworkManager 接管该网卡导致 IP 被重置，可执行 `nmcli device set usb0 managed no`。
- 界面缩放：`Ctrl + =` 放大、`Ctrl + -` 缩小、`Ctrl + 0` 复位（0.8~1.6 倍），
  比例保存在 `config.json` 的 `ui_scale`。

## 板卡与连接方式（写在外部 config.json）

程序支持管理多块板卡，每块板卡独立保存「连接方式 + SSH IP/端口/账号/密码」。连接方式分两种：

- **USB RNDIS**：通过 USB 数据线（Device 模式 Type-C）连接，板卡 IP 固定为 `192.168.55.1`
  （L4T RNDIS 默认网关），上位机自动检测 RNDIS 网卡并配置本机 IP。
- **局域网（LAN）**：板卡与上位机在同一局域网，直接通过板卡的局域网 IP 连接，无需 RNDIS。

SSH 账号、密码**不写在代码里**，而是放在程序目录下的外部文件 `config.json` 中。配置结构如下
（`boards` 为板卡列表，`active_board` 为当前选中的板卡名）：

```json
{
  "active_board": "局域网板卡",
  "boards": [
    {
      "name": "RNDIS 板卡",
      "mode": "rndis",
      "ssh_host": "192.168.55.1",
      "ssh_port": 22,
      "ssh_username": "<用户名>",
      "ssh_password": "<密码>"
    },
    {
      "name": "局域网板卡",
      "mode": "lan",
      "ssh_host": "<板卡局域网 IP>",
      "ssh_port": 22,
      "ssh_username": "<用户名>",
      "ssh_password": "<密码>"
    }
  ],
  "last_wifi_ssid": "",
  "last_wifi_password": "",
  "last_hotspot_ssid": "",
  "last_hotspot_password": "",
  "last_hotspot_autoconnect": true
}
```

> 以上为示例结构，部署时请将 `<用户名>`、`<密码>`、`<板卡局域网 IP>` 等占位符替换为实际值；
> 不要将含真实账号密码的 `config.json` 提交到仓库。

- `boards[].mode`：`rndis`（USB RNDIS）或 `lan`（局域网）。
- `boards[].ssh_host / ssh_port / ssh_username / ssh_password`：该板卡的 SSH 登录参数
  （sudo 命令也复用 `ssh_password` 作为 sudo 密码）。
- 顶部「板卡」下拉框切换当前板卡；「设置」按钮可添加/删除/编辑板卡（同样写回此文件）。
- 旧版扁平配置（`ssh_host` 等）会在首次启动时自动迁移为 `boards` 列表。
- 其余字段是「最近使用的 WiFi / 热点参数」，由程序自动保存，无需手动维护。

## 使用说明

1. 选择连接方式与板卡：在顶部「板卡」下拉框选择要配置的板卡（其连接方式显示在右侧）。
   - **USB RNDIS**：用 USB 数据线连接 Orin NX 的 Device 模式 Type-C 口与上位机；程序自动
     检测 RNDIS 网卡，若本机 IP 不是 `192.168.55.1` 同网段，按提示配置。
   - **局域网**：确认板卡已接入同一局域网，并在「设置」中填好其局域网 IP。
2. 启动程序，程序按当前板卡的连接方式自动处理（RNDIS 模式自动检测网卡，局域网模式跳过）。
3. 点击「连接」通过 SSH 登录板卡（账号密码取自当前板卡配置）。
4. 主界面左侧为导航栏，各页面：
   - **网络配置**（默认第一项）：内含 WiFi 配置 / IP 配置 / 热点配置三个子标签。
     - **WiFi 配置**：扫描可用 WiFi，双击列表项回填，输入密码后连接，成功后显示 WiFi IP。
     - **IP 配置**：选择要配置的连接，切换静态 IP / DHCP 并应用。
     - **热点配置**：启用/禁用热点、设置 SSID / 密码（≥8 位）/ 开机自启动。
   - **ROS 环境**：图形化管理远端 `~/.bashrc` 中激活的 ROS 环境（发行版 / 工作空间的
     `source …/setup.bash` 行），支持启用/禁用、添加、删除并写回（写入前自动备份原文件）。
   - **ROS 运行**：查询目标设备上运行中的 ROS 节点 / 话题 / 服务（ROS1 与 ROS2 自动识别），
     自动 source 所选发行版 setup.bash，并可一并 source 已启用的工作空间。
   - **系统服务**：管理远端 systemd 服务（列表 + 启动/停止/重启/启用/禁用），
     适用于让 ROS 节点开机自启等场景（可开关 sudo）。
   - **时钟同步**：检测 NTP 后端（chrony / systemd-timesyncd / ntpd），查看 timedatectl 与
     chronyc 状态，支持启用/禁用 NTP、添加 NTP 服务器、立即校时；「时间监测」子页持续采样
     远端与本机时钟偏移，绘图显示并自动标记/记录时间跳变事件。
   - **状态显示**：IP、WiFi 状态、CPU、内存、温度、GPU/功耗、磁盘、运行时间，默认每 4 秒
     自动刷新，可关闭自动刷新或调整刷新间隔；日志面板支持清空与导出完整日志文件。页面内含
     「任务管理器」子页，可查看远端进程的 PID / 用户 / CPU / 内存 / RSS / 命令。

## 打包（生成可执行文件）

PyInstaller 不支持交叉编译：Windows 包需在 Windows 上构建，Linux 包需在 Linux 上构建。

### Windows（exe）

用 `icon.svg` 生成的 `icon.ico` 作为程序图标与窗口图标。打包前先安装 PyInstaller 与 Pillow：

```bat
pip install pyinstaller pillow
build.bat
```

或手动执行：

```bat
python -m PyInstaller --noconfirm --clean --windowed --name "EmbededConfigurator" ^
  --icon icon.ico --add-data "ui/style.qss;ui" --add-data "icon.ico;." main.py
copy /y config.json "dist\EmbededConfigurator\config.json"
```

产物在 `dist\EmbededConfigurator\`：

- `EmbededConfigurator.exe` —— 主程序（已内嵌图标）
- `config.json` —— 在 exe 旁，可直接编辑登录账号/密码
- `_internal\ui\style.qss`、`_internal\icon.ico` —— 打包的资源文件

> 打包成单文件夹（one-folder）而非单文件，是为了让 `config.json` 保持为可编辑的外部文件。
> 若需重新生成图标：用 Qt 渲染 `icon.svg` 后经 Pillow 写出 `icon.ico`（见 `icon.ico` 生成过程）。

### Linux

```bash
pip install pyinstaller
./build.sh
```

产物在 `dist/EmbededConfigurator/`（可执行文件 `EmbededConfigurator`，图标使用 `icon.png`）。
目标机器需要提供 Qt 基础库，如 `libxcb-xinerama0`、`libxkbcommon-x11-0`、`libgl1`。

仓库内置 `.github/workflows/build-linux.yml`：推送 `v*` 标签（或手动触发）时，
在 ubuntu-22.04 上自动构建并上传 `EmbededConfigurator-linux-x86_64.tar.gz` 到对应 Release。

## 关键说明

- **保活**：SSH 连接启用了 keepalive（10s），避免 RNDIS / sshd 空闲或链路抖动导致的被动断开。
- **CPU 统计**：通过两次采样 `/proc/stat` 计算占用率，不依赖 `top`，避免无 TTY 环境卡住；
  占用率、用户/系统/IO 等待分别统计。
- **GPU / 功耗**：状态页通过 `tegrastats` 采样 GPU 占用（GR3D）、EMC、功耗与温度，
  不同 L4T 版本输出差异较大，解析尽量容错，提取不到的字段置空并在界面提示。
- **sudo**：nmcli 修改连接需 root 权限，程序用 `echo <密码> | sudo -S -p '' <cmd>`
  自动处理密码输入（使用 `config.json` 中的 `ssh_password` 作为 sudo 密码）。
- **单网卡角色**：同一张无线网卡通常不能同时做 STA（连 WiFi）与 AP（开热点），
  开启热点前请先断开 WiFi 客户端连接。
- **首次启动限制**：若 Orin NX 未完成 OOBE（初始用户创建），SSH 不可用，需先通过串口完成初始化。
- **界面缩放**：`Ctrl + =` 放大、`Ctrl + -` 缩小、`Ctrl + 0` 复位（0.8~1.6 倍），
  比例保存在 `config.json` 的 `ui_scale`；程序同时启用了 Qt 高 DPI 缩放，适配 125%/150%/200% 缩放屏。
- 日志保存在程序目录下 `embededconfigurator.log`，最近使用的参数保存在 `config.json`。
