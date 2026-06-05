#!/usr/bin/env python3
"""
Claude Lamp — lightweight hook for daemon mode.
Only writes state file; the daemon handles all serial communication.

Usage:
  python set_state.py working|idle|input|off
  python set_state.py --status

The daemon (claude_lamp_daemon.py) monitors the state file and sends
commands over a persistent serial connection — no ESP32 reset on every hook.
"""

import os
import sys
import tempfile
import time

TEMP = tempfile.gettempdir()
STATE_FILE = os.path.join(TEMP, "claude_lamp_state")
DAEMON_PID_FILE = os.path.join(TEMP, "claude_lamp_daemon.pid")
DAEMON_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "claude_lamp_daemon.py")
VALID_STATES = ("working", "idle", "input", "off")


def is_daemon_alive():
    """Check if daemon process is running (cross-platform)."""
    if not os.path.exists(DAEMON_PID_FILE):
        return False
    try:
        with open(DAEMON_PID_FILE) as f:
            pid = int(f.read().strip())

        if sys.platform == "win32":
            # Windows: use WaitForSingleObject with timeout 0
            import ctypes
            import ctypes.wintypes
            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_INFORMATION = 0x0400
            STILL_ACTIVE = 259
            handle = ctypes.windll.kernel32.OpenProcess(
                SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, pid)
            if not handle:
                raise OSError("process not found")
            exit_code = ctypes.wintypes.DWORD()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return exit_code.value == STILL_ACTIVE
        else:
            os.kill(pid, 0)
            return True
    except (ValueError, OSError):
        try:
            os.unlink(DAEMON_PID_FILE)
        except OSError:
            pass
        return False


def start_daemon():
    """Launch daemon in background if not already running."""
    if is_daemon_alive():
        return

    # Find python with pyserial
    import subprocess

    python_exe = sys.executable
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [python_exe, DAEMON_SCRIPT],
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def write_state(state):
    """Write desired state to state file."""
    try:
        with open(STATE_FILE, "w") as f:
            f.write(f"{state}\n{time.time()}")
    except OSError:
        pass


def hook_mode(state):
    """Write state file and ensure daemon is running."""
    write_state(state)

    # Try to start daemon if not running
    if not is_daemon_alive():
        start_daemon()


def show_status():
    """Print current status."""
    state = "(unknown)"
    try:
        with open(STATE_FILE) as f:
            raw = f.read().strip()
            state = raw.splitlines()[0] if raw else "(empty)"
    except FileNotFoundError:
        state = "(no state file)"

    daemon = "RUNNING" if is_daemon_alive() else "NOT RUNNING"

    print(f"State:   {state}")
    print(f"Daemon:  {daemon}")
    print(f"Port:    {os.environ.get('CLAUDE_LAMP_PORT', 'auto-detect')}")


def main():
    if len(sys.argv) < 2:
        show_status()
        return

    arg = sys.argv[1].lower()

    if arg == "--status":
        show_status()
    elif arg in VALID_STATES:
        hook_mode(arg)
    else:
        show_status()


if __name__ == "__main__":
    main()
