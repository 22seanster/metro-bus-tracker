// Metro Bus Tracker display client.
//
// Dumb client: every POLL_MS it GETs FRAME_URL (a 4104-byte binary frame:
// 8-byte header + 64x32 RGB565 little-endian pixels) and blits it to a HUB75
// panel. All layout/data logic lives in the backend; reflashing is never
// needed for new screens.
//
// First boot (or hold BOOT within 3s of power-up): opens a WiFi access point
// "BusTracker-Setup". Join it from a phone, pick your WiFi, and set the
// backend frame URL, e.g. http://192.168.1.50:8000/frame.bin

#include <Arduino.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiManager.h>

#include "pins.h"

static const uint16_t PANEL_W = 64;
static const uint16_t PANEL_H = 32;
static const uint32_t POLL_MS = 3000;
static const uint32_t HTTP_TIMEOUT_MS = 5000;
static const uint8_t MAX_FAILURES_BEFORE_NOTICE = 5;

static const size_t HEADER_SIZE = 8;
static const size_t PIXEL_BYTES = PANEL_W * PANEL_H * 2;

MatrixPanel_I2S_DMA *display = nullptr;
Preferences prefs;
char frameUrl[128] = "http://192.168.1.100:8000/frame.bin";
uint8_t pixelBuf[PIXEL_BYTES];
uint8_t failures = 0;
bool paramsDirty = false;

static void initDisplay() {
  HUB75_I2S_CFG::i2s_pins pins = {R1_PIN, G1_PIN, B1_PIN, R2_PIN, G2_PIN, B2_PIN,
                                  A_PIN,  B_PIN,  C_PIN,  D_PIN,  E_PIN,
                                  LAT_PIN, OE_PIN, CLK_PIN};
  HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1, pins);
  display = new MatrixPanel_I2S_DMA(cfg);
  display->begin();
  display->setBrightness8(128);
  display->clearScreen();
  display->setTextColor(display->color565(255, 255, 255));
}

static void showMessage(const char *line1, const char *line2 = nullptr) {
  display->clearScreen();
  display->setCursor(2, 4);
  display->print(line1);
  if (line2 != nullptr) {
    display->setCursor(2, 16);
    display->print(line2);
  }
}

static void saveParamsCallback() { paramsDirty = true; }

static void setupWiFi() {
  prefs.begin("bustracker", false);
  String stored = prefs.getString("frameUrl", frameUrl);
  stored.toCharArray(frameUrl, sizeof(frameUrl));

  WiFiManager wm;
  WiFiManagerParameter urlParam("frameurl", "Backend frame URL", frameUrl, sizeof(frameUrl) - 1);
  wm.addParameter(&urlParam);
  wm.setSaveParamsCallback(saveParamsCallback);
  wm.setConfigPortalTimeout(300); // reboot & retry stored creds after 5 min

  showMessage("WIFI", "SETUP...");
  if (!wm.autoConnect("BusTracker-Setup")) {
    showMessage("WIFI FAIL", "REBOOT..");
    delay(3000);
    ESP.restart();
  }

  if (paramsDirty) {
    strncpy(frameUrl, urlParam.getValue(), sizeof(frameUrl) - 1);
    frameUrl[sizeof(frameUrl) - 1] = '\0';
    prefs.putString("frameUrl", frameUrl);
  }
  showMessage("WIFI OK");
}

static bool fetchAndBlit() {
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(frameUrl)) return false;

  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    http.end();
    return false;
  }

  WiFiClient *stream = http.getStreamPtr();

  uint8_t header[HEADER_SIZE];
  size_t got = stream->readBytes(header, HEADER_SIZE);
  if (got != HEADER_SIZE || header[0] != 'M' || header[1] != 'B' || header[2] != 1 ||
      header[5] != PANEL_W || header[6] != PANEL_H) {
    http.end();
    return false;
  }
  uint8_t brightness = header[4];

  size_t received = 0;
  uint32_t deadline = millis() + HTTP_TIMEOUT_MS;
  while (received < PIXEL_BYTES && millis() < deadline) {
    size_t n = stream->readBytes(pixelBuf + received, PIXEL_BYTES - received);
    if (n == 0) break;
    received += n;
  }
  http.end();
  if (received != PIXEL_BYTES) return false;

  display->setBrightness8(brightness);
  for (uint16_t y = 0; y < PANEL_H; y++) {
    for (uint16_t x = 0; x < PANEL_W; x++) {
      size_t i = 2 * (y * PANEL_W + x);
      uint16_t color = pixelBuf[i] | (pixelBuf[i + 1] << 8); // little-endian
      display->drawPixel(x, y, color);
    }
  }
  return true;
}

static void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  showMessage("WIFI", "RETRY...");
  WiFi.reconnect();
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) delay(500);
}

void setup() {
  Serial.begin(115200);
  initDisplay();
  setupWiFi();
}

void loop() {
  ensureWiFi();

  if (fetchAndBlit()) {
    failures = 0;
  } else {
    if (failures < 255) failures++;
    Serial.printf("frame fetch failed (%u in a row) from %s\n", failures, frameUrl);
    if (failures == MAX_FAILURES_BEFORE_NOTICE) {
      showMessage("NO LINK", "CHECK SRV");
    }
  }

  delay(POLL_MS);
}
