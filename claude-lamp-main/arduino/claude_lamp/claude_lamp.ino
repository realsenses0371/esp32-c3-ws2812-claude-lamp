/*
 * Claude Lamp — ESP32-C3 firmware for WS2812B 24-LED ring.
 * Receives serial commands from claude_lamp.py / daemon.
 *
 * Commands (newline-terminated):
 *   WORKING  - comet chase animation (blue-white)
 *   IDLE     - solid warm orange
 *   INPUT    - red flashing (alert)
 *   OFF      - all LEDs off
 *
 * Sends "READY" once on startup for handshake.
 *
 * Target: ESP32-C3 Dev Module, GPIO10 → WS2812B DIN
 *
 * ⚠️ Arduino IDE 必须设置:
 *   工具 → USB CDC On Boot → Enabled
 */

#include <FastLED.h>

#define DATA_PIN  10        // ESP32-C3 GPIO10 → WS2812B DIN
#define NUM_LEDS  24        // 24颗灯珠圆形排列
#define LED_TYPE  WS2812B
#define COLOR_ORDER GRB

CRGB leds[NUM_LEDS];

enum State { ST_OFF, ST_IDLE, ST_INPUT, ST_WORKING };
State current_state = ST_OFF;
State prev_state    = ST_OFF;

// Animation globals for WORKING state
int  comet_pos = 0;
unsigned long last_comet_step = 0;
const unsigned long COMET_INTERVAL = 60;  // ms per step (~1.4s per revolution)

// Animation globals for INPUT state (red flashing)
unsigned long last_input_step = 0;
const unsigned long INPUT_INTERVAL = 400;  // ms per blink phase (400ms on / 400ms off)
bool input_leds_on = false;

// One-shot flag: true when a static state has already been drawn
bool static_drawn = false;

// Serial line buffer
char serial_buf[32];
byte serial_idx = 0;

void setup() {
  // USB CDC 模式下 Serial 走 USB，这里不需要 while(!Serial)
  Serial.begin(115200);

  // 等 USB 枚举完成 + LED 初始化
  delay(500);

  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS)
        .setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(120);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, 1500);  // 功率保护
  FastLED.clear();
  FastLED.show();

  Serial.println("READY");
}

void loop() {
  parse_serial();
  update_animation();
}

// ----------------------------------------------------------
// Serial parsing
// ----------------------------------------------------------

void parse_serial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serial_idx == 0) continue;
      serial_buf[serial_idx] = '\0';
      handle_command(serial_buf);
      serial_idx = 0;
    } else if (serial_idx < sizeof(serial_buf) - 1) {
      serial_buf[serial_idx++] = c;
    }
  }
}

void handle_command(const char* cmd) {
  if (strcmp(cmd, "WORKING") == 0) {
    current_state = ST_WORKING;
  } else if (strcmp(cmd, "IDLE") == 0) {
    current_state = ST_IDLE;
  } else if (strcmp(cmd, "INPUT") == 0) {
    current_state = ST_INPUT;
  } else if (strcmp(cmd, "OFF") == 0) {
    current_state = ST_OFF;
  }
  // Unknown commands silently ignored
}

// ----------------------------------------------------------
// Animation update (non-blocking)
// ----------------------------------------------------------

void update_animation() {
  // Detect state transition
  if (current_state != prev_state) {
    prev_state = current_state;
    static_drawn = false;
  }

  switch (current_state) {
    case ST_OFF:     update_off();     break;
    case ST_IDLE:    update_idle();    break;
    case ST_INPUT:   update_input();   break;
    case ST_WORKING: update_working(); break;
  }
}

// --- OFF ---
void update_off() {
  if (static_drawn) return;
  FastLED.clear();
  FastLED.show();
  static_drawn = true;
}

// --- IDLE: solid warm orange ---
void update_idle() {
  if (static_drawn) return;
  fill_solid(leds, NUM_LEDS, CRGB(255, 180, 50));
  FastLED.show();
  static_drawn = true;
}

// --- INPUT: red flashing (alert) ---
void update_input() {
  unsigned long now = millis();
  if (now - last_input_step < INPUT_INTERVAL) return;
  last_input_step = now;

  input_leds_on = !input_leds_on;

  if (input_leds_on) {
    fill_solid(leds, NUM_LEDS, CRGB(255, 0, 0));
  } else {
    FastLED.clear();
  }
  FastLED.show();
}

// --- WORKING: comet chase with 4-LED tail ---
void update_working() {
  unsigned long now = millis();
  if (now - last_comet_step < COMET_INTERVAL) return;
  last_comet_step = now;

  FastLED.clear();

  // Head color: blue-white
  leds[comet_pos] = CRGB(100, 150, 255);

  // Tail: 3 trailing LEDs at decreasing brightness
  leds[(comet_pos - 1 + NUM_LEDS) % NUM_LEDS] = CRGB(100, 150, 255).nscale8(102);
  leds[(comet_pos - 2 + NUM_LEDS) % NUM_LEDS] = CRGB(100, 150, 255).nscale8(38);
  leds[(comet_pos - 3 + NUM_LEDS) % NUM_LEDS] = CRGB(100, 150, 255).nscale8(13);

  FastLED.show();

  comet_pos = (comet_pos + 1) % NUM_LEDS;
}
