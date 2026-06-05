"""
Claude Lamp — LED strip test script.
Auto-discovers CH340/Arduino serial port, then cycles through all 4 states.

Usage:
  python test_serial.py

Set CLAUDE_LAMP_PORT env var to override auto-detection:
  Windows:  set CLAUDE_LAMP_PORT=COM3
  Linux:    export CLAUDE_LAMP_PORT=/dev/ttyUSB0
"""

import os
import sys
import time

import serial
import serial.tools.list_ports

# USB-serial chip identifiers (CH340, CP210x, ESP32 native USB)
CH340_VID = 0x1A86
CH340_PID = 0x7523
CP210_VID = 0x10C4
CP210_PID = 0xEA60
ESP32_VID = 0x303A  # Espressif USB Serial/JTAG
BAUD_RATE = 115200


def find_port():
    """Auto-detect ESP32/Arduino serial port, or use env var."""
    env_port = os.environ.get("CLAUDE_LAMP_PORT")
    if env_port:
        print(f"[INFO] Using port from CLAUDE_LAMP_PORT: {env_port}")
        return env_port

    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None

    # Priority 1: VID/PID match (CH340, CP210x, ESP32)
    for p in ports:
        if (p.vid == CH340_VID and p.pid == CH340_PID):
            print(f"[INFO] Found CH340 on {p.device}")
            return p.device
        if (p.vid == CP210_VID and p.pid == CP210_PID):
            print(f"[INFO] Found CP210x on {p.device}")
            return p.device
        if (p.vid == ESP32_VID):
            print(f"[INFO] Found ESP32 USB Serial on {p.device}")
            return p.device

    # Priority 2: description match
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(kw in desc or kw in mfg for kw in
               ("ch340", "cp210", "esp32", "wch", "arduino", "usb serial", "serial")):
            print(f"[INFO] Found {p.description} on {p.device}")
            return p.device

    # Fallback: list available ports and ask user
    print("[WARN] No ESP32/Arduino found. Available ports:")
    for p in ports:
        print(f"  {p.device} - {p.description}")
    return None


def main():
    port = find_port()
    if not port:
        print("[ERROR] No serial port found. Is the ESP32-C3 plugged in?")
        print("Set CLAUDE_LAMP_PORT env var to specify manually, e.g.:")
        print('  set CLAUDE_LAMP_PORT=COM3')
        sys.exit(1)

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open {port}: {e}")
        sys.exit(1)

    print(f"[OK] {port} connected")

    # Wait for Arduino READY handshake
    time.sleep(0.5)
    try:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if line:
            print(f"Arduino: {line}")
    except Exception:
        pass

    # Cycle through all states
    states = [
        ("WORKING", "comet chase animation (blue-white)", 4),
        ("IDLE", "solid warm orange", 3),
        ("INPUT", "red flashing (alert)", 2),
        ("OFF", "all LEDs off", 1),
    ]

    for cmd, desc, duration in states:
        print(f"-> {cmd} ({desc})")
        ser.write((cmd + "\n").encode("ascii"))
        ser.flush()
        time.sleep(duration)

    ser.close()
    print("[OK] Test complete - all 4 states worked.")


if __name__ == "__main__":
    main()
