#!/usr/bin/env bash
# EmbededConfigurator 启动脚本（Linux / macOS）
set -e
cd "$(dirname "$0")"
exec python3 main.py "$@"
