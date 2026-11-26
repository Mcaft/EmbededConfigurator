@echo off
rem ============================================================
rem  EmbededConfigurator build script (PyInstaller)
rem ============================================================
cd /d "%~dp0"

echo [1/2] Building with PyInstaller...
python -m PyInstaller --noconfirm --clean --windowed ^
  --name "EmbededConfigurator" ^
  --icon icon.ico ^
  --add-data "ui/style.qss;ui" ^
  --add-data "icon.ico;." ^
  main.py
if errorlevel 1 goto :err

echo [2/2] Copying config.json next to the exe...
copy /y config.json "dist\EmbededConfigurator\config.json" >nul

echo.
echo Done: dist\EmbededConfigurator\EmbededConfigurator.exe
goto :end

:err
echo Build FAILED!
pause
:end
