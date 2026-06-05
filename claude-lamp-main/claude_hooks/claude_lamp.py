#!/usr/bin/env python3
"""
Claude Lamp — direct serial hook for WS2812 LED ring.
Sends commands to Arduino via USB serial. No persistent daemon needed.

Usage:
  claude_lamp.exe working|idle|input|off    (hook mode)
  claude_lamp.exe --status                  (show status)
"""

import logging
import os
import sys
import tempfile
import time

import serial
import serial.tools.list_ports

TEMP = tempfile.gettempdir()
LOCK_FILE = os.path.join(TEMP, "claude_lamp.lock")
STATE_FILE = os.path.join(TEMP, "claude_lamp_state")
LOG_FILE = os.path.join(TEMP, "claude_lamp.log")

# USB-serial chip identifiers (CH340, CP210x, ESP32 native USB)
CH340_VID = 0x1A86
CH340_PID = 0x7523
CP210_VID = 0x10C4
CP210_PID = 0xEA60
ESP32_VID = 0x303A  # Espressif USB Serial/JTAG
BAUD_RATE = 115200
VALID_STATES = ("working", "idle", "input", "off")
LOCK_TIMEOUT = 3.0       # max seconds to wait for file lock
ARDUINO_RESET_WAIT = 1.5  # seconds to wait after opening port (ESP32-C3 reset)

log = logging.getLogger("claude_lamp")


# ----------------------------------------------------------
# Logging
# ----------------------------------------------------------

def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


# ----------------------------------------------------------
# Port discovery
# ----------------------------------------------------------

def find_port():
    env_port = os.environ.get("CLAUDE_LAMP_PORT")
    if env_port:
        return env_port

    ports = serial.tools.list_ports.comports()
    if not ports:
        return None

    # Priority 1: VID/PID match (CH340, CP210x, ESP32 USB Serial/JTAG)
    for p in ports:
        if (p.vid == CH340_VID and p.pid == CH340_PID) or \
           (p.vid == CP210_VID and p.pid == CP210_PID) or \
           (p.vid == ESP32_VID):
            return p.device

    # Priority 2: description match
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(kw in desc or kw in mfg for kw in
               ("ch340", "cp210", "esp32", "wch", "arduino", "usb serial", "serial")):
            return p.device

    return None


# ----------------------------------------------------------
# File-based lock (prevents concurrent COM port access)
# ----------------------------------------------------------

def acquire_lock():
    """Try to acquire the lock file. Returns True on success."""
    deadline = time.monotonic() + LOCK_TIMEOUT
    while time.monotonic() < deadline:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n{time.time()}".encode())
            os.close(fd)
            return True
        except FileExistsError:
            # Check if the existing lock is stale (> 30s)
            try:
                with open(LOCK_FILE) as f:
                    lines = f.read().strip().splitlines()
                if len(lines) >= 2:
                    lock_time = float(lines[1])
                    if time.time() - lock_time > 30:
                        os.unlink(LOCK_FILE)
                        continue
            except (ValueError, OSError):
                try:
                    os.unlink(LOCK_FILE)
                except OSError:
                    pass
                continue
            time.sleep(0.1)
    return False


def release_lock():
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass


# ----------------------------------------------------------
# Hook mode — open port, send command, close port
# ----------------------------------------------------------

STATE_CACHE_SECS = 5  # max age of cached state before force-resend

def hook_mode(state):
    """Write state file and send command directly to Arduino."""

    # Check if state is unchanged AND recently set — skip serial to avoid
    # Arduino reset. If the state file is older than STATE_CACHE_SECS,
    # force resend (covers session restarts where Arduino may have reset).
    try:
        with open(STATE_FILE) as f:
            lines = f.read().strip().splitlines()
        if len(lines) >= 2:
            prev_state = lines[0]
            prev_ts = float(lines[1])
            if prev_state == state and (time.time() - prev_ts) < STATE_CACHE_SECS:
                return  # Recently set to this state, skip
    except (FileNotFoundError, ValueError):
        pass

    # Write state file with timestamp
    try:
        with open(STATE_FILE, "w") as f:
            f.write(f"{state}\n{time.time()}")
    except OSError:
        pass

    setup_logging()
    log.info("Hook: %s", state)

    if not acquire_lock():
        log.info("Skipped (another hook in progress)")
        return

    try:
        port = find_port()
        if not port:
            log.warning("No port found")
            return

        ser = serial.Serial(port, BAUD_RATE, timeout=0.5)
        try:
            # ESP32-C3 resets on port open (DTR). Wait for boot + READY.
            # ESP32-C3 boot: ~300ms, then setup() delay(500) + Serial.println("READY")
            time.sleep(ARDUINO_RESET_WAIT)

            deadline = time.monotonic() + 2.0
            ready_seen = False
            while time.monotonic() < deadline:
                line = ser.readline()
                if line:
                    text = line.decode("ascii", errors="replace").strip()
                    if "READY" in text:
                        ready_seen = True
                        break

            if not ready_seen:
                # READY may have been sent before we started reading, or
                # ESP32 didn't reset. Just drain buffer and proceed.
                ser.reset_input_buffer()
            else:
                # Small delay after READY to ensure ESP32 enters main loop
                time.sleep(0.1)

            cmd = state.upper() + "\n"
            ser.write(cmd.encode("ascii"))
            ser.flush()
            log.info("Sent: %s (ready=%s)", state.upper(), ready_seen)

            # Brief pause to ensure transmission completes
            time.sleep(0.05)
        finally:
            ser.close()
    except serial.SerialException as e:
        log.error("Serial error: %s", e)
    finally:
        release_lock()


# ----------------------------------------------------------
# Status / diagnostics
# ----------------------------------------------------------

def show_status():
    """Show current state and port info."""
    setup_logging()

    state = "(none)"
    try:
        with open(STATE_FILE) as f:
            raw = f.read().strip()
            state = raw.splitlines()[0] if raw else "(empty)"
    except FileNotFoundError:
        pass

    locked = os.path.exists(LOCK_FILE)
    port = find_port()

    lines = [
        "=== Claude Lamp Status ===",
        "",
        f"Current state:  {state}",
        f"COM port:       {port or 'NOT FOUND'}",
        f"Port locked:    {'YES' if locked else 'NO'}",
        f"State file:     {STATE_FILE}",
        f"Lock file:      {LOCK_FILE}",
        f"Log file:       {LOG_FILE}",
    ]

    # Show last log entries
    try:
        with open(LOG_FILE) as f:
            tail = f.readlines()[-10:]
        if tail:
            lines.append("")
            lines.append("--- Last 10 log lines ---")
            lines.extend(line.rstrip() for line in tail)
    except FileNotFoundError:
        pass

    for line in lines:
        print(line)

    print()
    input("Press Enter to close...")


# ----------------------------------------------------------
# Entry point
# ----------------------------------------------------------

def main():
    arg = sys.argv[1].lower() if len(sys.argv) >= 2 else ""

    if arg == "--status":
        show_status()
    elif arg in VALID_STATES:
        hook_mode(arg)
    else:
        show_status()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Last resort: write crash info to temp file
        try:
            crash_file = os.path.join(TEMP, "claude_lamp_crash.txt")
            with open(crash_file, "w") as f:
                f.write(f"FATAL ERROR: {e}\n\n")
                import traceback
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise
