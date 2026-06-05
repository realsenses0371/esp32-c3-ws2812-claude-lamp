#include <FastLED.h>

#define NUM_LEDS    24
#define DATA_PIN    10        // ESP32-C3 的 GPIO10  45//
#define BRIGHTNESS  128
#define LED_TYPE    WS2812B
#define COLOR_ORDER GRB

CRGB leds[NUM_LEDS]; 

uint8_t  mode = 0;
uint32_t lastModeSwitch = 0;
const uint32_t MODE_HOLD_MS = 10000;
uint16_t gHue = 0;

// ---------- 函数原型（Forward Declarations） ----------
inline uint8_t wrap(int v, int m);
void fadeAll(uint8_t amount);
void runEffect(uint8_t m);

void effect_solidWheel();
void effect_rainbowCycle();
void effect_theaterChase();
void effect_larsonScanner();
void effect_comet();
void effect_breathe();
void effect_sparkleOnColor();
void effect_twinkle();
void effect_wipeClockwise();
void effect_dualPolice();   // ← 有原型，因此可在 runEffect 中调用
// -----------------------------------------------------

void setup() {
  delay(100);
  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, 1500);
  FastLED.clear(true);
}

void loop() {
  EVERY_N_MILLISECONDS(20) { gHue++; }  // 全局色相慢变

  runEffect(mode);
  FastLED.show();

  if (millis() - lastModeSwitch > MODE_HOLD_MS) {
    mode = (mode + 1) % 10;
    lastModeSwitch = millis();
  }
}

// ---------------- 工具函数 ----------------
inline uint8_t wrap(int v, int m) { int r = v % m; return r < 0 ? r + m : r; }
void fadeAll(uint8_t amount) { for (auto &p : leds) p.fadeToBlackBy(amount); }

// ---------------- 模式选择 ----------------
void runEffect(uint8_t m) {
  switch (m) {
    case 0: effect_solidWheel();     break;
    case 1: effect_rainbowCycle();   break;
    case 2: effect_theaterChase();   break;
    case 3: effect_larsonScanner();  break;
    case 4: effect_comet();          break;
    case 5: effect_breathe();        break;
    case 6: effect_sparkleOnColor(); break;
    case 7: effect_twinkle();        break;
    case 8: effect_wipeClockwise();  break;
    case 9: effect_dualPolice();     break;
  }
}

// ---------------- 10种灯效 ----------------
void effect_solidWheel() {
  fill_solid(leds, NUM_LEDS, CHSV(gHue, 255, 255));
}

void effect_rainbowCycle() {
  static uint8_t offset = 0;
  offset++;
  for (int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CHSV((i * 256 / NUM_LEDS) + offset, 255, 255);
  }
}

void effect_theaterChase() {
  static uint8_t q = 0;
  q = (q + 1) % 3;
  fadeAll(200);
  for (int i = q; i < NUM_LEDS; i += 3) {
    leds[i] = CHSV(gHue + 100, 200, 255);
  }
  delay(50);
}

void effect_larsonScanner() {
  static int8_t dir = 1;
  static int i = 0;
  fadeAll(150);
  leds[i] = CRGB::Red;
  leds[wrap(i-1, NUM_LEDS)].setRGB(64,0,0);
  leds[wrap(i+1, NUM_LEDS)].setRGB(64,0,0);
  i += dir;
  if (i == NUM_LEDS-1 || i == 0) dir = -dir;
  delay(20);
}

void effect_comet() {
  static uint8_t head = 0;
  fadeAll(60);
  leds[head] = CHSV(gHue, 255, 255);
  head = (head + 1) % NUM_LEDS;
  delay(18);
}

void effect_breathe() {
  float s = (sin(millis() / 900.0) + 1.0) * 0.5;  // 0~1
  uint8_t v = 30 + uint8_t(225 * s);
  fill_solid(leds, NUM_LEDS, CHSV(gHue, 80, v));
}

void effect_sparkleOnColor() {
  fill_solid(leds, NUM_LEDS, CHSV(gHue, 120, 60));
  int i = random8(NUM_LEDS);
  leds[i] = CHSV(gHue + random8(40, 80), 200, 255);
  delay(40);
}

void effect_twinkle() {
  fadeAll(20);
  if (random8() < 40) {
    int i = random8(NUM_LEDS);
    leds[i] += CHSV(random8(), 200, 255);
  }
  delay(20);
}

void effect_wipeClockwise() {
  static uint8_t idx = 0;     // ← 修正：不是 ui
  leds[idx] = CHSV(gHue + idx * 8, 200, 255);
  idx = (idx + 1) % NUM_LEDS;
  delay(25);
}

void effect_dualPolice() {
  fadeAll(120);
  static uint8_t k = 0; k++;
  uint8_t iA = k % NUM_LEDS;
  uint8_t iB = (iA + NUM_LEDS/2) % NUM_LEDS;
  leds[iA] = CRGB::Blue;
  leds[wrap(iA-1, NUM_LEDS)] += CRGB(0,0,64);
  leds[iB] = CRGB::Red;
  leds[wrap(iB+1, NUM_LEDS)] += CRGB(64,0,0);
  delay(18);
}
