@echo off
setlocal
echo === Building claude_lamp.exe for Windows ===

REM Check prerequisites
python --version >nul 2>&1 || (
    echo ERROR: Python not found. Install Python 3.8+ from python.org
    exit /b 1
)

echo.
echo [1/3] Installing dependencies...
pip install pyserial pyinstaller || (
    echo ERROR: pip install failed
    exit /b 1
)

echo.
echo [2/3] Building single-file exe with PyInstaller...
pyinstaller ^
    --onefile ^
    --name claude_lamp ^
    --hidden-import serial.tools.list_ports_windows ^
    --hidden-import serial.tools.list_ports ^
    --clean ^
    "claude_hooks\claude_lamp.py" || (
    echo ERROR: PyInstaller build failed
    exit /b 1
)

echo.
echo [3/3] Copying exe to claude_hooks\...
copy /Y "dist\claude_lamp.exe" "claude_hooks\claude_lamp.exe" >nul

echo.
echo SUCCESS: claude_hooks\claude_lamp.exe is ready.
echo.
echo Next steps:
echo   1. Copy claude_lamp.exe to %%USERPROFILE%%\.claude\claude_lamp_hooks\
echo   2. Merge settings.windows.json into %%USERPROFILE%%\.claude\settings.json
echo   3. Restart Claude Code

endlocal
