#!/usr/bin/env bash
# EmbededConfigurator build script (Linux, PyInstaller)
set -e
cd "$(dirname "$0")"

python3 -m PyInstaller --noconfirm --clean --windowed \
  --name "EmbededConfigurator" \
  --icon icon.png \
  --add-data "ui/style.qss:ui" \
  --add-data "icon.png:." \
  --add-data "icon.svg:." \
  main.py

echo "Done: dist/EmbededConfigurator/EmbededConfigurator"
