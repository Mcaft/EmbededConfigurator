@echo off
rem Orin NX 地面站配置工具启动脚本
cd /d "%~dp0"
python main.py
if errorlevel 1 pause
