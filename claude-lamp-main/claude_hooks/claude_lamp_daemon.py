#!/usr/bin/env python3
"""
Claude Lamp serial daemon — maintains persistent USB serial connection
to ESP32-C3 and responds to state changes written to the state file.

States: working, idle, input, off

Unlike claude_lamp.py (direct mode), this daemon opens the serial port ONCE
and keeps it open. This avoids the ESP32-C3 resetting (DTR) on every command.
"""

import logging
import os
import signal
import sys
import tempfile
import time

import serial
import serial.tools.list_ports

TEMP = tempfile.gettempdir()
PID_FILE = os.path.join(TEMP, "claude_lamp_daemon.pid")
STATE_FILE = os.path.join(TEMP, "claude_lamp_state")
LOG_FILE = os.path.join(TEMP, "claude_lamp_daemon.log")

IDLE_TIMEOUT = 30 * 60  # 30 minutes
BAUD_RATE = 115200

# USB-serial chip identifiers (CH340, CP210x, ESP32 native USB)
CH340_VID = 0x1A86
CH340_PID = 0x7523
CP210_VID = 0x10C4
CP210_PID = 0xEA60
ESP32_VID = 0x303A  # Espressif USB Serial/JTAG

log = logging.getLogger("claude_lamp_daemon")


def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


# ----------------------------------------------------------
# Singleton lock (cross-platform, no fcntl)
# ----------------------------------------------------------

def _pid_alive(pid):
    """Check if a process is running (cross-platform)."""
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes
        SYNCHRONIZE = 0x00100000
        PROCESS_QUERY_INFORMATION = 0x0400
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            return False
        exit_code = ctypes.wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == STILL_ACTIVE
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def acquire_lock():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return False      # another daemon is alive
            os.unlink(PID_FILE)   # stale PID file
        except (ValueError, OSError):
            try:
                os.unlink(PID_FILE)
            except OSError:
                pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    try:
        os.unlink(PID_FILE)
    except OSError:
        pass


# ----------------------------------------------------------
# Serial port auto-detection
# ----------------------------------------------------------

def find_port():
    """Find ESP32/Arduino serial port. Checks env var first, then VID/PID,
    then description substring match."""

    env_port = os.environ.get("CLAUDE_LAMP_PORT")
    if env_port:
        log.info("Using port from CLAUDE_LAMP_PORT: %s", env_port)
        return env_port

    ports = serial.tools.list_ports.comports()
    if not ports:
        return None

    # Priority 1: VID/PID match (CH340, CP210x, ESP32 USB Serial/JTAG)
    for p in ports:
        if (p.vid == CH340_VID and p.pid == CH340_PID) or \
           (p.vid == CP210_VID and p.pid == CP210_PID) or \
           (p.vid == ESP32_VID):
            log.info("Found known chip on %s (VID:%04X PID:%04X)", p.device, p.vid, p.pid)
            return p.device

    # Priority 2: description match
    for p in ports:
        desc = p.description.lower() if p.description else ""
        mfg = (p.manufacturer or "").lower()
        if any(kw in desc or kw in mfg for kw in
               ("ch340", "cp210", "esp32", "wch", "arduino", "usb serial", "serial")):
            log.info("Found device on %s (%s)", p.device, p.description)
            return p.device

    return None


def wait_for_port():
    """Block until a port is found, retrying every 5 seconds."""
    while True:
        port = find_port()
        if port:
            return port
        log.warning("No ESP32/Arduino port found, retrying in 5s...")
        time.sleep(5)


# ----------------------------------------------------------
# Serial communication
# ----------------------------------------------------------

def wait_for_ready(ser, timeout=3.0):
    """Wait for 'READY' handshake from Arduino after port open."""
    original_timeout = ser.timeout
    ser.timeout = timeout
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        try:
            b = ser.read(1)
            if b:
                buf.extend(b)
                if b == b'\n':
                    line = buf.decode("ascii", errors="replace").strip()
                    log.info("Arduino says: %s", line)
                    if "READY" in line:
                        ser.timeout = original_timeout
                        return True
                    buf = bytearray()
        except serial.SerialException:
            break
    ser.timeout = original_timeout
    return False


def send_command(ser, cmd):
    """Send a newline-terminated command to the Arduino."""
    data = (cmd + "\n").encode("ascii")
    log.info("TX %s", cmd)
    ser.write(data)
    ser.flush()


# ----------------------------------------------------------
# State file reading
# ----------------------------------------------------------

def read_state():
    try:
        with open(STATE_FILE) as f:
            raw = f.read().strip()
            return raw.splitlines()[0] if raw else ""
    except FileNotFoundError:
        return ""


# ----------------------------------------------------------
# Main loop
# ----------------------------------------------------------

def main():
    setup_logging()

    if not acquire_lock():
        log.info("Another daemon already running, exiting")
        sys.exit(0)

    log.info("Daemon starting (pid=%d)", os.getpid())

    shutdown = False

    def handle_signal(signum, _frame):
        nonlocal shutdown
        log.info("Received signal %d, shutting down", signum)
        shutdown = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    port_name = wait_for_port()
    ser = None

    current_state = ""
    idle_since = None

    try:
        while not shutdown:
            # Ensure serial port is open
            if ser is None or not ser.is_open:
                try:
                    if ser and ser.is_open:
                        ser.close()
                except Exception:
                    pass
                try:
                    ser = serial.Serial(port_name, BAUD_RATE, timeout=0.1)
                    log.info("Opened serial port %s", port_name)
                    wait_for_ready(ser)
                except serial.SerialException as e:
                    log.error("Cannot open %s: %s", port_name, e)
                    ser = None
                    time.sleep(5)
                    continue

            # Read desired state from file
            desired = read_state()

            if desired != current_state:
                log.info("State: %s -> %s", current_state, desired)
                current_state = desired
                idle_since = None

                try:
                    if current_state == "idle":
                        send_command(ser, "IDLE")
                        idle_since = time.monotonic()
                    elif current_state == "input":
                        send_command(ser, "INPUT")
                    elif current_state == "working":
                        send_command(ser, "WORKING")
                    elif current_state == "off":
                        send_command(ser, "OFF")
                        break
                except serial.SerialException as e:
                    log.error("Serial write error: %s", e)
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None

            # Idle timeout
            if current_state == "idle" and idle_since is not None:
                if time.monotonic() - idle_since >= IDLE_TIMEOUT:
                    log.info("Idle timeout reached, shutting down")
                    try:
                        if ser and ser.is_open:
                            send_command(ser, "OFF")
                    except Exception:
                        pass
                    break

            time.sleep(0.2)

    finally:
        # Graceful shutdown
        if ser and ser.is_open:
            try:
                send_command(ser, "OFF")
                ser.close()
            except Exception as e:
                log.warning("Shutdown error: %s", e)
        release_lock()
        log.info("Daemon exited")


if __name__ == "__main__":
    main()
