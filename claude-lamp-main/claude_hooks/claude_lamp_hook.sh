#!/usr/bin/env bash
# Claude Lamp hook for Arduino WS2812 ring.
# Usage: claude_lamp_hook.sh <working|idle|input|off>
# Always exits 0 to never block Claude Code.

set -e

STATE="${1:-idle}"
PID_FILE="/tmp/claude_lamp_daemon.pid"
STATE_FILE="/tmp/claude_lamp_state"
DAEMON="$(cd "$(dirname "$0")" && pwd)/claude_lamp_daemon.py"

# 1. Write desired state
printf '%s' "$STATE" > "$STATE_FILE"

# 2. If daemon is alive, nothing more to do
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        exit 0
    fi
    rm -f "$PID_FILE"
fi

# 3. Auto-detect python with pyserial
PYTHON=""
if python3 -c "import serial" 2>/dev/null; then
    PYTHON="python3"
elif /opt/homebrew/bin/python3 -c "import serial" 2>/dev/null; then
    PYTHON="/opt/homebrew/bin/python3"
elif [ -n "$CONDA_PREFIX" ] && "$CONDA_PREFIX/bin/python3" -c "import serial" 2>/dev/null; then
    PYTHON="$CONDA_PREFIX/bin/python3"
fi

if [ -z "$PYTHON" ]; then
    echo "[claude_lamp] No python with pyserial found, skipping" >> /tmp/claude_lamp_daemon.log
    exit 0
fi

# 4. Launch daemon
nohup "$PYTHON" "$DAEMON" >> /tmp/claude_lamp_daemon.log 2>&1 &
echo $! > "$PID_FILE"

exit 0
