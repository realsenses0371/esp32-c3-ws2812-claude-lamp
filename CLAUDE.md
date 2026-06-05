# CLAUDE.md — ESP32-C3 WS2812 圆形状态灯

## 项目概述

用 WS2812B 24 颗圆形灯带作为 Claude Code 的物理状态指示器。ESP32-C3 通过 USB-C 连接电脑，接收串口指令切换灯效。

| 状态 | 灯效 | Claude Code 钩子触发时机 |
|---|---|---|
| WORKING | 蓝白色彗星追逐 | PreToolUse、UserPromptSubmit |
| IDLE | 暖橙色常亮 | SessionStart、Stop、idle_prompt |
| INPUT | 红色闪烁 | PreToolUse(AskUserQuestion)、PermissionRequest |
| OFF | 全部熄灭 | SessionEnd |

## 架构（重要）

两种运行模式，**Windows 上必须用守护进程模式**：

### 守护进程模式（当前使用）⭐
```
Hook → set_state.py（只写 %TEMP%\claude_lamp_state）
       → claude_lamp_daemon.py（串口常开，200ms 轮询状态文件）
              → ESP32-C3
```
- 串口只打开一次，ESP32 不会反复复位
- 钩子只写文本文件，极快、不会出错
- Hook 指令：`python "绝对路径/set_state.py" working|idle|input|off`

### 直接模式（不推荐在 Windows 上）
```
Hook → claude_lamp.py（打开串口→发指令→关串口）
       → ESP32-C3（每次打开串口都复位！）
```
- 每次调用 ESP32 都复位（DTR 触发），约 800ms boot 时间
- 钩子频繁触发时 ESP32 不断复位，灯带无法稳定显示

## 硬件

- ESP32-C3 开发板（集成 24 颗 WS2812B）
- 数据引脚：GPIO10
- 供电：USB-C 直连（5V）
- VID:PID = 303A:1001（Espressif USB Serial/JTAG）

## 关键文件

```
项目/
├── arduino/claude_lamp/claude_lamp.ino    # ESP32 固件
├── claude_hooks/
│   ├── set_state.py                       # ★ 钩子入口：只写状态文件
│   ├── claude_lamp_daemon.py              # ★ 守护进程：串口常开
│   ├── claude_lamp.py                     # 直接模式（备用）
│   ├── claude_lamp.exe                    # PyInstaller 打包（已废弃不用）
│   └── claude_lamp_hook.sh                # macOS/Linux shell 钩子
├── test_serial.py                         # 独立测试脚本，验证硬件正常
└── README.md
```

## 串口协议

115200 波特率，换行分隔命令：
- `WORKING\n` → 彗星追逐
- `IDLE\n` → 暖橙常亮
- `INPUT\n` → 红色闪烁
- `OFF\n` → 熄灭
- ESP32 启动后发送 `READY\n`

## 状态文件和日志

都在 `%TEMP%`（Windows）或 `/tmp/`（macOS/Linux）：
- `claude_lamp_state` — 当前期望状态（第一行）
- `claude_lamp_daemon.pid` — 守护进程 PID
- `claude_lamp_daemon.log` — 守护进程日志
- `claude_lamp.log` — 直接模式日志
- `claude_lamp.lock` — 串口访问锁

## 钩子配置

配置文件：`~/.claude/settings.json`（用户级，全局生效）

关键 env：
- `CLAUDE_LAMP_PORT` = `COM35`（当前端口，换 USB 口时需更新）

## 已解决的问题（2026-06-05）

1. **灯带不亮** — 直接模式下钩子频繁打开串口导致 ESP32 反复复位。改用守护进程模式。
2. **`os.kill(pid, 0)` Windows 不兼容** — `os.kill` 在 Windows 上不支持 signal 0。改用 Windows API：`OpenProcess` + `GetExitCodeProcess` 检测进程存活。`claude_lamp_daemon.py` 和 `set_state.py` 都已修复。
3. **回答完问题灯带延迟切换** — PostToolUse AskUserQuestion 设置了 `input`，覆盖了用户刚回答的状态。改为 `working`。
4. **COM 口锁死** — Windows 底层锁住 COM35（PermissionError）。需要拔插 USB 线释放端口。

## 故障排查

### 灯带不亮
```bash
# 1. 检查硬件
python test_serial.py

# 2. 检查守护进程
cat $TEMP/claude_lamp_daemon.log

# 3. 检查当前状态
python "项目路径/claude_hooks/set_state.py" --status

# 4. 手动设置状态
python "项目路径/claude_hooks/set_state.py" working
```

### COM 口被锁（PermissionError）
拔掉 ESP32 USB 线，等 3 秒，插回去。

### 守护进程挂了
```bash
# 杀掉所有 Python 进程重启
powershell -Command "Stop-Process -Name python -Force"
rm $TEMP/claude_lamp_daemon.pid
# 重新启动 Claude Code，或手动启动守护进程
nohup python "项目路径/claude_hooks/claude_lamp_daemon.py" &
```

### 查看串口是否识别
```bash
python -c "import serial.tools.list_ports; [print(p.device, p.description) for p in serial.tools.list_ports.comports()]"
```
