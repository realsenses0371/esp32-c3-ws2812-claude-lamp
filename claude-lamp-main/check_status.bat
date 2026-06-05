@echo off
echo === Claude Lamp Status ===
echo.
echo Temp directory: %TEMP%
echo.

if exist "%TEMP%\claude_lamp_daemon.log" (
    echo --- Daemon Log ---
    type "%TEMP%\claude_lamp_daemon.log"
    echo.
) else (
    echo No log file found. Daemon may not have started yet.
    echo.
)

if exist "%TEMP%\claude_lamp_state" (
    set /p STATE=<"%TEMP%\claude_lamp_state"
    echo Current state: %STATE%
) else (
    echo No state file.
)

if exist "%TEMP%\claude_lamp_daemon.pid" (
    echo PID file exists.
) else (
    echo PID file not found (daemon not running).
)

echo.
echo --- Serial Ports ---
python -c "import serial.tools.list_ports; [print(f'  {p.device} - {p.description} (VID:{p.vid}, PID:{p.pid})') for p in serial.tools.list_ports.comports()]" 2>nul || echo "  (pyserial not installed)"

pause
