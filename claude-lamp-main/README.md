# Claude Lamp — ESP32-C3 WS2812 环形状态指示灯

把圆形 LED 灯带变成 Claude Code 的物理状态指示器：工作时彗星追逐动画，空闲时暖橙色常亮，需要你输入时红色闪烁。

## 效果演示

| 状态 | 灯带效果 | 触发时机 |
|---|---|---|
| **工作中** | 蓝白色彗星追逐动画 | 提交 Prompt、使用工具（Read、Write、Bash 等） |
| **空闲** | 暖橙色常亮 (255, 180, 50) | Claude 回复完毕、会话启动 |
| **等待输入** | 红色闪烁 | 权限请求、Plan 审批、询问问题、通知 |
| **关闭** | 全部熄灭 | 会话结束 |

## 硬件清单 (BOM)

| 元件 | 规格 | 数量 |
|---|---|---|
| 开发板 | ESP32-C3 WS2812 圆形灯带板（24 颗灯珠，GPIO10） | 1 |
| USB 数据线 | Type-C | 1 |

**总成本：约 15–30 元**

> 这块板子集成了 ESP32-C3 主控 + 24 颗 WS2812B，无需外接灯带和杜邦线，一根 USB-C 线即可使用。

## 接线

无需外接连线。开发板通过 USB-C 直连电脑即可：
- **供电 + 数据** 一根 USB-C 线搞定
- **LED 数据引脚** 板载 GPIO10（固件中已配置）
- **LED 数量** 24 颗（固件中已配置）

## 快速开始

### 0. 准备工作

- Python 3.8+
- Arduino IDE（[下载](https://www.arduino.cc/en/software)）
- [pyserial](https://pypi.org/project/pyserial/)：`pip install pyserial`
- ESP32 开发板支持：Arduino IDE → 文件 → 首选项 → 附加开发板管理器网址，添加：
  ```
  https://espressif.github.io/arduino-esp32/package_esp32_index.json
  ```

### 1. 烧录固件

1. 打开 **Arduino IDE**
2. 安装 **FastLED** 库：`工具 → 管理库 → 搜索 "FastLED" → 安装`
3. 安装 ESP32 开发板：`工具 → 开发板 → 开发板管理器 → 搜索 "esp32" → 安装 "esp32 by Espressif Systems"`
4. 打开 `arduino/claude_lamp/claude_lamp.ino`
5. 配置开发板：**工具 → 开发板** → "ESP32C3 Dev Module"
6. 配置端口：选择对应的 COM 口
7. 点击 **上传**（如果上传失败，按住板上的 BOOT 键再点上传）
8. 打开串口监视器（波特率 115200）— 应看到 `READY`

### 2. 测试连接

```sh
python test_serial.py
```

灯带应依次展示：彗星追逐 → 橙色常亮 → 红色闪烁 → 熄灭。

脚本会自动检测串口。如果自动检测失败，手动指定端口：

```sh
# Windows (CMD)
set CLAUDE_LAMP_PORT=COM3

# Windows (PowerShell)
$env:CLAUDE_LAMP_PORT = "COM3"

# macOS / Linux
export CLAUDE_LAMP_PORT=/dev/ttyUSB0
```

执行以下命令可查看当前可用串口：

```sh
python -c "import serial.tools.list_ports; [print(p.device, p.description) for p in serial.tools.list_ports.comports()]"
```

### 3. 配置 Claude Code Hooks

将 `claude_hooks/settings.windows.json`（或 `settings.json`）中的 hooks 配置复制到 **用户级** settings.json：

- **Windows** — `%USERPROFILE%\.claude\settings.json`
- **macOS / Linux** — `~/.claude/settings.json`

**重要：** 所有 `command` 路径必须改为你电脑上的 **绝对路径**。示例：

```json
"command": "python \"D:/projects/esp32-c3-ws2812-claude-lamp/claude_hooks/set_state.py\" working"
```

同时在 `env` 中指定串口（可选，自动检测失败时兜底）：

```json
"env": {
  "CLAUDE_LAMP_PORT": "COM3"
}
```

> ⚠️ 如果全局 settings.json 已有其他配置，只追加 `env.CLAUDE_LAMP_PORT` 和 `hooks` 字段，不要覆盖已有内容。

### 4. 重启 Claude Code

重启 Claude Code 即可。首次 hook 事件触发时，会自动连接 ESP32-C3。

### 5. 更换 COM 口

开发板插到不同 USB 口时端口号会变化。修改 settings.json 中 `env.CLAUDE_LAMP_PORT` 即可：

```json
"env": {
  "CLAUDE_LAMP_PORT": "COM4"
}
```

删掉该字段则恢复自动检测（支持 CH340 / CP210x / ESP32 USB Serial/JTAG）。

## 工作原理

```
Claude Code hook 事件
  → settings.json 触发命令：python set_state.py working
    → set_state.py 写入状态到临时文件（极快，不碰串口）
      → claude_lamp_daemon.py 守护进程（串口常开，200ms 轮询状态文件）
        → ESP32-C3 解析命令，更新 LED 动画
```

**守护进程模式（推荐，全平台通用）：**

1. `set_state.py` — hook 调用的入口，只写状态文件，毫秒级完成
2. `claude_lamp_daemon.py` — 后台守护进程，维持串口常开，轮询状态文件变化

串口只打开一次，ESP32 不会反复复位，状态切换延迟 <200ms。

**直接模式（备用，macOS/Linux）：**

`claude_lamp.py` 直接打开串口→发指令→关串口。每次调用约 1–1.5 秒。Windows 上不推荐（打开串口会触发 ESP32 复位）。

## 项目结构

```
├── CLAUDE.md                          # 项目文档（Claude Code 自动加载）
├── arduino/
│   └── claude_lamp/
│       └── claude_lamp.ino            # ESP32-C3 固件（FastLED + WS2812B）
├── Arduino测试代码/
│   └── ESP32_C3_WS2812/
│       └── ESP32_C3_WS2812.ino        # 10种灯效测试固件
├── claude_hooks/
│   ├── set_state.py                   # ★ Hook 入口（只写状态文件，毫秒级）
│   ├── claude_lamp_daemon.py          # ★ 守护进程（串口常开，200ms 轮询）
│   ├── claude_lamp.py                 # 直接模式（备用）
│   ├── claude_lamp_hook.sh            # macOS/Linux shell hook
│   ├── settings.json                  # Hook 配置模板（macOS/Linux）
│   └── settings.windows.json          # Hook 配置模板（Windows）
├── test_serial.py                     # 独立测试脚本：循环展示所有灯效
├── build_exe.bat                      # PyInstaller 打包脚本（可选）
├── check_status.bat                   # 诊断工具：查看状态 + 串口列表
├── ESP32_C3_WS2812.png                # 硬件照片
├── ESP32_C3_WS2812.pdf                # 硬件原理图
├── 尺寸图.png                          # 尺寸图纸
├── LICENSE                            # MIT
└── README.md
```

## 串口协议

ESP32-C3 在 **115200** 波特率下接收换行分隔的命令：

| 命令 | 灯带效果 |
|---|---|
| `WORKING` | 彗星追逐动画：蓝白色头部 + 3 颗渐暗拖尾，每步 60ms |
| `IDLE` | 暖橙色常亮（24 颗全亮） |
| `INPUT` | 红色闪烁（24 颗全亮） |
| `OFF` | 全部熄灭 |

启动时 ESP32-C3 发送 `READY` 作为握手信号。

## 自定义

**修改灯珠数量：** 编辑 `claude_lamp.ino` 中的 `NUM_LEDS`（第 19 行）。默认 24。

**修改数据引脚：** 编辑 `claude_lamp.ino` 中的 `DATA_PIN`（第 18 行）。默认 GPIO10。

**修改动画速度：** 编辑 `claude_lamp.ino` 中的 `COMET_INTERVAL`（第 30 行），数值越小追逐越快。

**修改颜色：** 编辑 `update_*()` 函数中的 `CRGB(...)` 值：
- `update_working()` — 彗星头部和拖尾颜色
- `update_idle()` — 空闲状态颜色
- `update_input()` — 等待输入状态颜色

**修改亮度：** 编辑 `setup()` 中的 `FastLED.setBrightness(120)`（第 51 行），范围 0–255。

## 常见问题

### 灯带不亮

1. 检查 ESP32-C3 是否被识别：
   ```sh
   python -c "import serial.tools.list_ports; [print(p.device, p.description) for p in serial.tools.list_ports.comports()]"
   ```
2. 手动运行 `python test_serial.py`，排除 hook 的问题
3. 检查守护进程状态：
   ```sh
   python claude_hooks/set_state.py --status
   ```
4. 查看守护进程日志：
   - Windows：`type %TEMP%\claude_lamp_daemon.log`
   - macOS / Linux：`cat /tmp/claude_lamp_daemon.log`
5. 如果守护进程挂了，杀掉残留进程后重启 Claude Code：
   ```sh
   # Windows
   powershell -Command "Stop-Process -Name python -Force"
   del %TEMP%\claude_lamp_daemon.pid
   # macOS / Linux
   kill "$(cat /tmp/claude_lamp_daemon.pid)"
   rm -f /tmp/claude_lamp_daemon.pid
   ```
6. 确认固件已烧录：按一下板上的 RESET 键，串口监视器应显示 `READY`

### 串口未能自动检测

手动指定端口：
```sh
# Windows (CMD)
set CLAUDE_LAMP_PORT=COM3

# Windows (PowerShell)
$env:CLAUDE_LAMP_PORT = "COM3"

# macOS / Linux
export CLAUDE_LAMP_PORT=/dev/ttyUSB0
```

或在 `.claude/settings.json` 中添加 `"env": {"CLAUDE_LAMP_PORT": "COM3"}`。

### ESP32-C3 无响应

1. 打开 Arduino IDE 串口监视器（115200 波特率）
2. 手动发送 `IDLE` — 如果灯带亮了，说明固件正常，问题在 hook 链路
3. 确认固件已烧录：按一下板上的 RESET 键，串口监视器应显示 `READY`
4. 如果上传后灯带一直不亮，检查 GPIO10 是否与你的板子引脚一致

### 端口被占用 / 拒绝访问

有其他程序占用了 COM 口（如 Arduino IDE 串口监视器、另一个 Claude Code 会话等）。关闭后重试。

### 上传失败

ESP32-C3 上传时需要进入下载模式：
1. 按住 **BOOT** 键不放
2. 点击 Arduino IDE 的 **上传** 按钮
3. 看到 "Connecting..." 后松开 BOOT 键
4. 如果仍失败，尝试同时按住 BOOT + RESET，先松 RESET 再松 BOOT

### Windows：COM 口被锁（PermissionError）

拔掉 ESP32 USB 线，等 3 秒，插回去。如果还不行，用 PowerShell 杀掉占用进程后重试。

### macOS / Linux：守护进程管理

```sh
# 查看守护进程状态
cat /tmp/claude_lamp_daemon.log

# 终止卡住的守护进程
kill "$(cat /tmp/claude_lamp_daemon.pid)"
rm -f /tmp/claude_lamp_daemon.pid /tmp/claude_lamp_state
```

## 许可证

MIT
