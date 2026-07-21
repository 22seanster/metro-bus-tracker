// Metro Bus Tracker display client.
//
// Dumb client: it GETs FRAME_URL (a 4104-byte binary frame: 8-byte header +
// 64x32 RGB565 little-endian pixels) and blits it to a HUB75 panel, at a
// cadence the backend advertises in header byte [7]. All layout/data logic
// lives in the backend; reflashing is never needed for new screens.
//
// First boot: opens a WiFi access point "BusTracker-Setup". Join it from a
// phone, pick your WiFi, and set the backend frame URL, e.g.
// http://192.168.1.50:8000/frame.bin

#include <Arduino.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <ArduinoJson.h>
#include <HTTPUpdate.h>
#include <esp_ota_ops.h>

#include "pins.h"

#ifndef FW_BUILD
#define FW_BUILD 0            // CI overrides via -D FW_BUILD=<git commit count>
#endif
#ifndef FW_SHA
#define FW_SHA "dev"          // CI overrides via -D FW_SHA=<short sha>
#endif

// Stringify helpers so the build identity is embedded in the binary itself.
#define _FW_STR(x) #x
#define FW_STR(x) _FW_STR(x)
// CI greps this marker to prove the compiled-in build number matches the
// build number it advertises in latest.json. Never remove it.
static const char FW_VERSION_MARKER[] __attribute__((used)) =
    "FWID build=" FW_STR(FW_BUILD) " sha=" FW_SHA;

static const uint16_t PANEL_W = 64;
static const uint16_t PANEL_H = 32;
// Poll cadence. The backend advertises one in header byte [7] (0 = "use your
// default", else 10ms units) so animated screens can ask us to keep up without
// paying for a fast poll the rest of the time.
static const uint32_t POLL_MS_DEFAULT = 3000;
// Hard floor. delay() below is loop()'s only unconditional yield, and
// vTaskDelay(0) does not force one, so a backend bug must never be able to
// starve the idle task and trip the 5s task watchdog.
static const uint32_t POLL_MS_MIN = 40;
static const uint32_t POLL_MS_MAX = 10000;
static uint32_t pollMs = POLL_MS_DEFAULT;
static const uint32_t HTTP_TIMEOUT_MS = 5000;
static const uint8_t MAX_FAILURES_BEFORE_NOTICE = 5;
// An image that cannot fetch frames never validates (see
// markFirmwareValidIfPending), and without a reboot the bootloader never gets
// to roll it back. Reboot an unproven image after this many failures so the
// rollback can actually happen.
static const uint8_t MAX_FAILURES_BEFORE_UNVALIDATED_REBOOT = 20;

static const uint32_t OTA_CHECK_MS = 15UL * 60UL * 1000UL; // 15 min
static const uint32_t OTA_FIRST_CHECK_MS = 30UL * 1000UL;  // ~30 s after boot
static uint32_t nextOtaCheck = OTA_FIRST_CHECK_MS;
static bool firmwareValidated = false;
static const uint8_t MAX_OTA_ATTEMPTS = 3;

static const size_t HEADER_SIZE = 8;
static const size_t PIXEL_BYTES = PANEL_W * PANEL_H * 2;

MatrixPanel_I2S_DMA *display = nullptr;
Preferences prefs;
char frameUrl[128] = "http://192.168.1.100:8000/frame.bin";
uint8_t pixelBuf[PIXEL_BYTES];
uint8_t failures = 0;
bool paramsDirty = false;
// False when the HUB75 DMA engine failed to initialise. Drawing is skipped in
// that state, but WiFi and the OTA check still run — a bad build that breaks
// the panel can then be replaced over the air instead of needing a USB cable.
bool displayReady = false;

static void initDisplay() {
#ifdef BOARD_S3
  // Waveshare ESP32-S3-RGB-Matrix: keep the DMA library's ESP32-S3 default
  // HUB75 pins, then apply the two deviations Waveshare's own examples make
  // (waveshareteam/ESP32-S3-RGB-Matrix, 01_SimpleTestShapes):
  //  - E is hardwired to GPIO 9 on this board. The stock library default is -1
  //    (Waveshare patched their vendored copy to 9). Unused on this 1/16-scan
  //    64x32 panel, but set for correctness and 64-row panel portability.
  //  - clkphase=false (library default is true -> inverted pixel clock). A
  //    wrong phase shows as the image shifted by one column / ghost pixels.
  // SHIFTREG is vendor-required for the P4 panel.
  HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1);
  cfg.driver = HUB75_I2S_CFG::SHIFTREG;
  cfg.gpio.e = 9;
  cfg.clkphase = false;
#else
  HUB75_I2S_CFG::i2s_pins pins = {R1_PIN, G1_PIN, B1_PIN, R2_PIN, G2_PIN, B2_PIN,
                                  A_PIN,  B_PIN,  C_PIN,  D_PIN,  E_PIN,
                                  LAT_PIN, OE_PIN, CLK_PIN};
  HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1, pins);
#endif
  display = new MatrixPanel_I2S_DMA(cfg);
  // Waveshare's own Arduino example checks this return value: begin() allocates
  // the DMA buffers and fails if there is not enough (internal) RAM. PSRAM is
  // not enabled on this board target, so that allocation comes out of the
  // ~512 KB internal SRAM and a failure here is the realistic one. Without this
  // check a failure looks identical to dead hardware — a black panel, no clue.
  displayReady = display->begin();
  if (!displayReady) {
    Serial.println("FATAL: HUB75 DMA memory allocation failed (begin() returned "
                   "false); panel disabled, continuing so WiFi/OTA still run");
    return;
  }
  display->setBrightness8(128);
  display->clearScreen();
  display->setTextColor(display->color565(255, 255, 255));
}

static void showMessage(const char *line1, const char *line2 = nullptr) {
  if (!displayReady) return;
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
  // Only updated behind a valid header, so a failed fetch keeps the last good
  // cadence rather than inheriting garbage.
  pollMs = header[7] ? constrain((uint32_t)header[7] * 10UL, POLL_MS_MIN, POLL_MS_MAX)
                     : POLL_MS_DEFAULT;

  size_t received = 0;
  // Rollover-safe deadline, same idiom as the OTA timer in loop().
  uint32_t deadline = millis() + HTTP_TIMEOUT_MS;
  while (received < PIXEL_BYTES && (int32_t)(millis() - deadline) < 0) {
    size_t n = stream->readBytes(pixelBuf + received, PIXEL_BYTES - received);
    if (n == 0) break;
    received += n;
  }
  http.end();
  if (received != PIXEL_BYTES) return false;

  if (displayReady) {
    display->setBrightness8(brightness);
    for (uint16_t y = 0; y < PANEL_H; y++) {
      for (uint16_t x = 0; x < PANEL_W; x++) {
        size_t i = 2 * (y * PANEL_W + x);
        uint16_t color = pixelBuf[i] | (pixelBuf[i + 1] << 8); // little-endian
        display->drawPixel(x, y, color);
      }
    }
  }
  // Deliberately still true when the panel is dead: a complete frame did arrive.
  // This is what lets markFirmwareValidIfPending() confirm a freshly-OTA'd image.
  // Returning false here would leave every new image unvalidated, so the
  // bootloader would roll it back and the device would re-download it forever —
  // and a failed begin() is a memory/hardware condition a rollback cannot fix.
  return true;
}

static void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  showMessage("WIFI", "RETRY...");
  WiFi.reconnect();
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) delay(500);
}

// Called once after the first good frame fetch post-boot. If we booted a
// freshly-OTA'd image in the PENDING_VERIFY state, mark it valid so it becomes
// permanent; otherwise this is a harmless no-op.
static void markFirmwareValidIfPending() {
  if (firmwareValidated) return;
  firmwareValidated = true;
  const esp_partition_t *running = esp_ota_get_running_partition();
  esp_ota_img_states_t state;
  if (esp_ota_get_state_partition(running, &state) == ESP_OK &&
      state == ESP_OTA_IMG_PENDING_VERIFY) {
    esp_ota_mark_app_valid_cancel_rollback();
    // This boot is the first good frame fetch after a fresh OTA flash, i.e.
    // the update just succeeded. Clear the retry-tracking state so it doesn't
    // linger forever: a subsequent *failing* release must start its count at
    // zero, not inherit whatever was left behind by this device's OTA
    // history. A plain power-cycle boot never reaches this branch at all
    // (the running partition is only ESP_OTA_IMG_PENDING_VERIFY immediately
    // after a fresh OTA flash, before it has been confirmed), so a genuinely
    // failing release's count still survives ordinary reboots untouched.
    prefs.putInt("otaFailCount", 0);
    prefs.putString("otaFailSha", "");
    Serial.println("OTA image marked valid");
  }
}

// "http://host:8000/frame.bin" -> "http://host:8000"
static bool baseUrlFromFrameUrl(const char *url, char *out, size_t outSize) {
  const char *tail = strstr(url, "/frame.bin");
  if (tail == nullptr) return false;
  size_t len = (size_t)(tail - url);
  if (len == 0 || len >= outSize) return false;
  memcpy(out, url, len);
  out[len] = '\0';
  return true;
}

// Fetches the server's advertised release (build + sha) into *build/sha.
// Returns false on any error (network failure, non-200, malformed JSON, or a
// missing "build"/"sha" key) and leaves *build/sha untouched; the caller
// treats false as "no update available" and must not touch DMA on this path.
static bool fetchServerRelease(const char *baseUrl, long *build, char *sha, size_t shaSize) {
  char url[160];
  snprintf(url, sizeof(url), "%s/firmware/latest.json", baseUrl);
  HTTPClient http;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(url)) return false;
  int code = http.GET();
  if (code != HTTP_CODE_OK) { http.end(); return false; }
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getString());
  http.end();
  if (err) return false;

  if (doc["build"].isNull() || doc["sha"].isNull() || !doc["sha"].is<const char *>()) return false;
  const char *shaVal = doc["sha"].as<const char *>();
  // Reject a null or empty sha: "" doubles as the "no abandon record"
  // sentinel (see otaFailSha below), so an empty-sha release would collide
  // with that sentinel and could get permanently stuck at the retry cap.
  if (shaVal == nullptr || shaVal[0] == '\0') return false;

  *build = doc["build"].as<long>();
  strncpy(sha, shaVal, shaSize - 1);
  sha[shaSize - 1] = '\0';
  return true;
}

static void checkForUpdate() {
  char base[128];
  if (!baseUrlFromFrameUrl(frameUrl, base, sizeof(base))) {
    Serial.println("OTA: disabled - frame URL doesn't end in /frame.bin, can't derive firmware host");
    return;
  }

  long serverBuild = -1;
  char serverSha[32] = {0};
  if (!fetchServerRelease(base, &serverBuild, serverSha, sizeof(serverSha))) return; // no server firmware / error
  if (serverBuild <= FW_BUILD) return;         // strictly-greater rule

  // Track repeated failures per server *release*, keyed on sha rather than
  // build: build is git rev-list --count HEAD, which is not guaranteed
  // monotonic or unique across a rebase/force-push/branch switch, so a
  // repeated build number must not inherit a stale abandon record from a
  // different, earlier release that happened to number the same. This keeps
  // a poisoned release from wearing out flash with an endless
  // download/flash/reboot loop, while a genuinely new release (different
  // sha, even with the same build number) is always retried from a clean
  // slate.
  String otaFailSha = prefs.getString("otaFailSha", "");
  int otaFailCount = prefs.getInt("otaFailCount", 0);
  if (!otaFailSha.equals(serverSha)) {
    otaFailSha = serverSha;
    otaFailCount = 0;
  }
  if (otaFailCount >= MAX_OTA_ATTEMPTS) {
    Serial.printf("OTA: build %ld sha %s failed %d times; giving up until a new release appears\n",
                  serverBuild, serverSha, otaFailCount);
    return;
  }
  otaFailCount++;
  prefs.putString("otaFailSha", otaFailSha);
  prefs.putInt("otaFailCount", otaFailCount);

  Serial.printf("OTA: server build %ld sha %s > mine %d; updating (attempt %d/%d)\n",
                serverBuild, serverSha, FW_BUILD, otaFailCount, MAX_OTA_ATTEMPTS);
  showMessage("UPDATING", "...");

  char binUrl[160];
  snprintf(binUrl, sizeof(binUrl), "%s/firmware.bin", base);

  // The download is the worst case for S3 WiFi-vs-DMA EMI: quiet the panel.
  // NOTE: stopDMAoutput() is one-way in this library version — the panel stays
  // black until reboot — so every path below this line must end in a reboot.
  if (displayReady) display->stopDMAoutput();
  WiFiClient client;
  httpUpdate.rebootOnUpdate(true);             // reboots into new image on success
  t_httpUpdate_return ret = httpUpdate.update(client, binUrl);

  // Only reached if the update did NOT reboot (i.e. it failed). The panel is
  // dead at this point, so restart to restore the display and resume normally.
  Serial.printf("OTA did not reboot (ret=%d, err=%d: %s); restarting\n",
                (int)ret, httpUpdate.getLastError(),
                httpUpdate.getLastErrorString().c_str());
  delay(2000);                                 // let the serial line flush
  ESP.restart();
}

void setup() {
  Serial.begin(115200);
  Serial.printf("boot: build=%d sha=%s\n", FW_BUILD, FW_SHA);
  // __attribute__((used)) keeps the compiler from dropping FW_VERSION_MARKER,
  // but this toolchain's linker runs with --gc-sections, which can still
  // discard an otherwise-unreferenced rodata section. Actually reading the
  // symbol here (not just the macro values) guarantees it survives into the
  // final binary, where CI's `strings | grep` check depends on finding it.
  Serial.println(FW_VERSION_MARKER);
  initDisplay();
  setupWiFi();

  // If the last boot left a nonzero OTA failure count behind, this device
  // just failed an update - don't hammer it again 30s after reboot.
  if (prefs.getInt("otaFailCount", 0) > 0) {
    nextOtaCheck = OTA_CHECK_MS;
  }
}

void loop() {
  ensureWiFi();

  bool ok = fetchAndBlit();
  if (ok) {
    failures = 0;
    markFirmwareValidIfPending();
  } else {
    if (failures < 255) failures++;
    Serial.printf("frame fetch failed (%d in a row) from %s\n", failures, frameUrl);
    if (failures == MAX_FAILURES_BEFORE_NOTICE) {
      showMessage("NO LINK", "CHECK SRV");
    }
    // Only for an image that has never proven itself: reboot so the bootloader
    // can roll back to the last known-good one. Gating on !firmwareValidated
    // matters — an ordinary server outage must not turn into a reboot loop.
    if (!firmwareValidated && failures >= MAX_FAILURES_BEFORE_UNVALIDATED_REBOOT) {
      Serial.println("unvalidated image cannot fetch frames; rebooting for rollback");
      delay(100);  // let the line flush
      ESP.restart();
    }
  }

  // Rollover-safe timer: comparing (int32_t)(millis() - nextOtaCheck) >= 0
  // is safe across the ~49.7-day millis() wrap. The naive form millis() >=
  // nextOtaCheck fails: when rescheduled near UINT32_MAX, nextOtaCheck wraps
  // small while millis() is still large, causing the check to fire repeatedly
  // until millis() also wraps ~15 min later.
  int32_t otaOverdueBy = (int32_t)(millis() - nextOtaCheck);
  if (otaOverdueBy >= 0) {
    if (WiFi.status() == WL_CONNECTED) {
      nextOtaCheck = millis() + OTA_CHECK_MS;
      checkForUpdate();
    } else if (otaOverdueBy > (int32_t)OTA_CHECK_MS) {
      // WiFi has been down long enough that nextOtaCheck is more than a full
      // check interval in the past. Re-anchor to "now" so millis() -
      // nextOtaCheck can't keep growing toward INT32_MAX (~24.8 days), which
      // would otherwise make the rollover-safe comparison above go dormant
      // for another ~24.8 days once it wraps negative. A shorter outage still
      // retries promptly via the fallthrough below.
      nextOtaCheck = millis();
    }
    // else: leave nextOtaCheck as-is so a check skipped due to WiFi being
    // momentarily down retries promptly instead of waiting a full 15 min.
  }

  // Failure path always uses the slow default: a dead server must not be
  // hammered 20x/sec just because the last good frame asked for a fast cadence.
  delay(ok ? pollMs : POLL_MS_DEFAULT);
}
