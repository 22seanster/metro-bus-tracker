# Hardware — Bill of Materials & Decisions

_Last updated: 2026-07-18. Records the hardware chosen for the physical build,
why, and the firmware follow-ups it implies. Written so a future session (Claude
Code or otherwise) has the full context without re-deriving it._

_**Assembly status:** built and powered on 2026-07-18. The panel lights and the
board boots. Sections marked **VERIFIED ON HARDWARE** were confirmed against the
physical build; everything else is still as-planned. The pre-build guesses about
the driver board's power connectors were **wrong** — see "Power" and "Assembly"
below for what the board actually has._

## Design goals that drove these choices

- **No soldering.** The builder is new to hardware; every connection must be
  plug-in or screw-terminal.
- **Kitchen-shelf display, readable from up to ~10 feet.**
- **Reuse the existing architecture.** The device stays a "dumb frame client":
  the Dockerized backend renders a 64×32 RGB565 image and serves `/frame.bin`;
  the device fetches it over WiFi every few seconds and blits it. No backend or
  frame-protocol changes are needed for the new hardware.

## Final bill of materials (ordered July 2026, ~$76 total)

| Component | Product (as ordered) | Key specs | Price | Source / ASIN |
|---|---|---|---|---|
| Driver board (controller) | **Waveshare ESP32-S3-RGB-Matrix** ("ESP32-S3 RGB Matrix Driver Board") | ESP32-S3-N32R16, 32MB flash / 16MB PSRAM, WiFi+BLE, female HUB75 socket, **two USB-C ports (`POWER` + `USB`)**, **5V/GND copper post bus**, onboard RTC/IMU/mics | $34.55 | Amazon (Waveshare, SKU 34422) |
| LED panel | **Waveshare 64×32 RGB LED Matrix, P4 (4mm pitch)** | 64×32 (2048 px), HUB75, 1/16 scan, ~256×128 mm, includes chaining ribbon + VH4 power pigtail | $31.67 | Amazon B0B3W1PFY6 |
| Power supply | ~~**YiKaiEn 5V 5A (25W)**, screw-terminal + 5.5×2.5mm barrel~~ **Not needed** — see Power below | 5V DC, 5A, UL-type brick, US plug | $9.99 | Amazon B0FDRSWL8T |

Total as ordered: **$76.21**. The 5V/5A brick turned out to be unnecessary —
the build runs on a USB-C charger. Keep it as a fallback if brightness ever
outgrows USB-C.

**Correction (2026-07-18):** the driver board row above originally read
"screw-terminal 5V in + USB-C". That was wrong. The board has **no screw
terminal and no barrel jack**.

## Key decisions & rationale

### Controller: Waveshare ESP32-S3-RGB-Matrix (chosen)

- **No soldering:** panel connects via ribbon + screw-terminal power; board ships assembled.
- **Firmware reuse:** the board runs the *same* `ESP32-HUB75-MatrixPanel-DMA`
  library the current firmware already uses, so it should be close to drop-in
  (mainly a pin remap — see TODOs). This was the deciding factor over the Adafruit
  MatrixPortal S3, which would have required a full rewrite to Adafruit Protomatter.
- **Availability:** in stock with (slower) shipping while the MatrixPortal S3 was
  out of stock with manufacturing lead times almost everywhere as of July 2026.
- **Spec headroom:** ESP32-S3 with 32MB flash / 16MB PSRAM — far more than a 4KB
  frame client needs, but useful future-proofing.

### Alternatives considered and rejected

- **Adafruit MatrixPortal S3** — cleanest flush-mount and best docs, but (a) chronically
  out of stock / long lead times in mid-2026, and (b) does **not** play well with the
  `ESP32-HUB75-MatrixPanel-DMA` library over WiFi (documented I2S/DMA-vs-WiFi EMI on its
  PCB). Its native path is Protomatter, which would mean rewriting the firmware. Still a
  fine fallback if the Waveshare board disappoints.
- **ESP32-Trinity (Brian Lough / Makerfabs)** — the *safest* "known-good, zero firmware
  change" option (classic ESP32-WROOM, no S3 WiFi-EMI issue, years of Tidbyt-style builds).
  Rejected only because it ships from China (slow) and the builder wanted fast US shipping.
  Keep as the backup if the Waveshare board has WiFi trouble.

### Panel size/aspect: 64×32, P4 (4mm) pitch (chosen)

- **Resolution is fixed at 64×32** by the backend renderer — not a free choice.
- **Aspect 2:1 (landscape)** suits a departure-board layout and keeps text tall; it's the
  Tidbyt-style standard the content is built around. A square 64×64 was rejected: it would
  shrink text at the same physical size and require reworking the backend render size/layouts.
- **P4 pitch for 10-foot readability:** with the ~16px-tall glyphs this project uses, P4 gives
  ~2.5" characters (≈256×128 mm panel) — effortless at 10 ft. P3 was borderline for small text
  at that distance; P5 (~320×160 mm) reads even better but is a bigger shelf footprint than wanted.

### Power: USB-C into the board's `POWER` port — **VERIFIED ON HARDWARE**

The board has **no screw terminal and no barrel jack**. Its power interfaces are:

- **Two USB-C ports**, silkscreened **`POWER`** and **`USB`**.
- **Two copper posts** silkscreened **`5V`** and **`GND`**, each with a screw. These are the
  shared 5V bus, *not* mounting standoffs — the HUB75 connector carries the mechanical load.
  Fork/spade terminals land under the post screws (this is what the panel pigtail's forks are for).

**Working topology (built and confirmed 2026-07-18):**

```
USB-C charger → board `POWER` port → board's 5V bus
                                      ├→ runs the ESP32-S3
                                      └→ `5V`/`GND` posts → VH4 pigtail → panel `VCC`/`GND`

Board's female HUB75 socket plugs DIRECTLY onto the panel's male `IN` header (data).
```

- **USB-C alone powers the whole assembly, panel included.** Waveshare's own user guide lists a
  **27W USB-C PSU as a required component**, which is the intended power path. Confirmed working.
- Note that 27W USB-C PD is typically only **5V/3A (15W)** at 5V — the 27W headline comes from
  higher-voltage PD profiles. 3A is still ample for this project's sparse, mostly-black screens.
  Use a genuine 27W-class charger, not a 1A phone brick; a marginal supply causes flaky resets,
  not a clean failure.
- **The earlier claim that "USB-C is for flashing only" was wrong** and has been removed. It was
  based on the assumption that the board had a screw terminal for wall power. It does not.
- The wires from the posts to the panel are required **regardless** of the power source — the
  posts are how power leaves the board to reach the panel's LEDs.
- **Open item:** USB-C power was validated against Waveshare's demo firmware, which may be dimmer
  or sparser than this project's screens. Re-check for brownouts/resets on the first sustained run
  of real content at real brightness. The 5V/5A brick is the fallback if it proves marginal.
- Panel draw for reference: ~1.5–3A typical, ~4A worst case (full white, max brightness). This
  project never approaches full white.

## Firmware follow-ups (TODO when hardware arrives)

The current firmware (`firmware/`) targets a classic ESP32 (`board = esp32dev`) using the DMA
library's **classic-ESP32** default pins (R1=25, G1=26, B1=27, R2=14, G2=12, B2=13, A=23, B=19,
C=5, D=17, LAT=4, OE=15, CLK=16). Moving to the Waveshare ESP32-S3 board needs the following.
The backend, frame protocol, and the "fetch `/frame.bin` and blit" client logic are **unchanged** —
only the board target and the panel init.

### 1. PlatformIO board target

Change the env from `esp32dev` to an ESP32-S3 target (e.g. `board = esp32-s3-devkitc-1`), keeping
the same `mrfaptastic/ESP32 HUB75 LED MATRIX PANEL DMA Display` and WiFiManager deps. The board is
an ESP32-S3-N32R16 (octal PSRAM); PSRAM isn't required for a 4KB frame, but if enabled, the library
will use `SPIRAM_DMA_BUFFER` automatically.

### 2. HUB75 pins — do NOT hardcode; use the library's ESP32-S3 defaults

Key finding: Waveshare's own Arduino examples construct the panel with **no custom pin map**
(`HUB75_I2S_CFG mxconfig(64, 32, 1);`) and comment *"Keep ESP32-S3 default HUB75 mapping to avoid
Flash/PSRAM reserved pins."* So the board is wired to the DMA library's built-in **ESP32-S3**
defaults. Delete any explicit `i2s_pins` from the config and let it default. (The old classic-ESP32
pins above must NOT be reused — several, e.g. 23/25, don't even exist on the S3.)

For reference, the library's ESP32-S3 default pins (from
`src/platforms/esp32s3/esp32s3-default-pins.hpp`) are:

| Signal | GPIO | Signal | GPIO | Signal | GPIO |
|---|---|---|---|---|---|
| R1 | 4 | R2 | 7 | A | 18 |
| G1 | 5 | G2 | 15 | B | 8 |
| B1 | 6 | B2 | 16 | C | 3 |
| LAT | 40 | OE | 2 | D | 42 |
| CLK | 41 | | | E | **9 on this board** (library default -1; see 2026-07-19 re-check) |

Sanity check on first boot: the library logs each GPIO it uses at `begin()` — confirm they match
this table, and cross-check the current example `.ino` in the Waveshare GitHub repo in case a
library version bumps the defaults.

### 3. REQUIRED for this P4 panel: set the shift-register driver

Waveshare's docs: *"When driving a P4 series panel, be sure to add
`mxconfig.driver = HUB75_I2S_CFG::SHIFTREG;` … otherwise display anomalies may occur."* Set it.
(It is the library's default driver, but set it explicitly per Waveshare. Do **not** set `FM6126A`
/ `FM6124` unless a future panel actually needs it.)

Resulting init looks like:

```cpp
HUB75_I2S_CFG mxconfig(64, 32, 1);        // width, height, chain — no custom pins
mxconfig.driver = HUB75_I2S_CFG::SHIFTREG; // required for the Waveshare P4 panel
dma_display = new MatrixPanel_I2S_DMA(mxconfig);
dma_display->begin();
dma_display->setBrightness8(128);          // brightness is server-controlled in this project
```

### 4. Open risk: WiFi stability under DMA (test early)

The S3's WiFi radio can be disturbed by HUB75 DMA EMI (documented for S3 boards generally). If frame
fetches become flaky once the panel is lit, mitigations in order:

- **Correction (verified against the pinned library source, v3.0.15):** the library exposes only a
  **one-way** `stopDMAoutput()` — its own doc comment says *"Screen will forever be black until next
  ESP reboot."* There is no `resumeDMAoutput()` or other resume/restart counterpart anywhere in this
  library version (the underlying bus class has an internal `dma_transfer_start()`, but it is not
  exposed publicly). That rules out wrapping each routine `/frame.bin` fetch in
  stop → fetch → resume — there is no way to resume without rebooting, and rebooting every 3 seconds
  is not viable. The mitigation is therefore usable **only** around the firmware's OTA download, which
  already ends in a reboot either way (into the new image on success, or via an explicit `ESP.restart()`
  if the update fails) — see `firmware/src/main.cpp`'s `checkForUpdate()`. It does **not** apply to the
  steady-state per-frame fetch loop.
- Lower brightness; confirm the onboard antenna (we bought the standard, not the u.FL variant).
- Last resort: fall back to the **ESP32-Trinity** (classic ESP32, no S3 EMI issue, runs the current
  firmware unchanged) or rewrite onto Adafruit **Protomatter**.

This is the main open unknown in the hardware plan; validate it before finishing the enclosure.

## Vendor documentation cross-check (2026-07-18)

The firmware decisions above were checked against Waveshare's official wiki
([overview](https://docs.waveshare.com/ESP32-S3-RGB-Matrix),
[instructions](https://docs.waveshare.com/ESP32-S3-RGB-Matrix/Instructions-For-Use),
[Arduino setup](https://docs.waveshare.com/ESP32-S3-RGB-Matrix/Development-Environment-Setup-Arduino),
[FAQ](https://docs.waveshare.com/ESP32-S3-RGB-Matrix/FAQ)).

**Confirmed by the vendor:**

- **`SHIFTREG` is mandatory for P4.** Verbatim: *"be sure to add
  `mxconfig.driver = HUB75_I2S_CFG::SHIFTREG;` in the code, otherwise display
  anomalies may occur."* Their example also leaves `FM6126A` commented out.
- **Do not hardcode HUB75 pins.** Verbatim: *"Keep ESP32-S3 default HUB75
  mapping to avoid Flash/PSRAM reserved pins."* Note that **no HUB75 GPIO table
  is published on any page of the wiki** — the overview, Resources, and ESP-IDF
  pages all omit one. Hardcoding pins would be guesswork against reserved
  flash/PSRAM lines, so relying on the library defaults is the only safe path.
  (The table in §2 above comes from the DMA library source, not from Waveshare.)
- **USB-C is the intended power source, not just a flashing cable.** The
  Instructions page lists the required PSU as *"PSU-27W-USB-C-EU-B x 1 USB Type-C
  charger."* This supersedes an earlier claim in this document that USB-C was
  flashing-only and would brown out the panel — that was wrong. The board is
  also documented as programmed over USB, consistent with `USB` (flashing) and
  `POWER` (supply) being separate ports.
- **Default brightness 128** matches the vendor's stated default.

**Operational facts worth knowing (from the FAQ):**

- **Brownout threshold:** *"the USB supply voltage should be above 4.9V."* Below
  that, the board resets in a loop and the USB port re-enumerates repeatedly.
  That symptom means power, not firmware.
- **Download-mode recovery** when flashing fails: hold **BOOT**, press and
  release **RESET**, release **BOOT**.
- A reset loop after upload can also mean *"the additional screen power supply"*
  (the VH4 pigtail) is not connected.

**Open discrepancy — Arduino core version:**

Waveshare's Arduino page specifies core **esp32 by Espressif Systems 3.3.7**.
This project pins `platform = espressif32@7.0.1`, which resolves to
`framework-arduinoespressif32 3.20017.241212` — Arduino core **2.0.17**
(confirmed via `ESP_ARDUINO_VERSION_MAJOR/MINOR/PATCH` in
`cores/esp32/esp_arduino_version.h`). That is a full major version behind: 2.x
is built on ESP-IDF 4.4, 3.x on ESP-IDF 5.x.

It compiles cleanly and the S3 GDMA code path is active, so this is not known to
be a problem — but it is an untested combination for this board. **If the panel
misbehaves in a way the wiring doesn't explain, this is the first thing to
change.** Bumping it crosses an ESP-IDF major version and would put the
`esp_ota_*` rollback calls, `HTTPUpdate`, and WiFiManager back in play, so it
needs a full rebuild and re-verification rather than a one-line edit.

## Vendor documentation re-check (2026-07-19) — GitHub repo findings

A deeper pass against Waveshare's official example repo
(`github.com/waveshareteam/ESP32-S3-RGB-Matrix`), which turned out to contain the
board data the wiki omits. These findings are applied in `firmware/` as of this
date.

- **E is hardwired to GPIO 9.** The wiki publishes no pin table, but the repo
  does: every Arduino example vendors a patched `esp32s3-default-pins.hpp` with
  `E_PIN_DEFAULT 9` *and* sets `mxconfig.gpio.e = 9;` explicitly; the IDF
  example's `sdkconfig.defaults` confirms with `CONFIG_HUB75_PIN_E=9`. The other
  13 pins match the DMA library's stock ESP32-S3 defaults (table in §2) exactly.
  The firmware now sets `cfg.gpio.e = 9;` — unused on this 1/16-scan 64×32 panel
  but correct, and required if a 64-row panel is ever attached.
- **`clkphase = false`.** Waveshare's examples set `mxconfig.clkphase = false;`;
  the library default is `true` (inverted pixel clock — it feeds
  `bus_cfg.invert_pclk` on the S3 code path). Adopted. If the image ever shows a
  one-column shift or ghost edge pixels, this is the knob that was wrong.
- **Serial must go over native USB (CDC).** UART0's pins are consumed by onboard
  peripherals — GPIO 43 (U0TXD) is I2S SCLK, GPIO 44 (U0RXD) is SD CMD — and the
  board has no USB-UART bridge. The PlatformIO `esp32-s3-devkitc-1` target
  defaults `ARDUINO_USB_CDC_ON_BOOT=0` (Serial → UART0), which would make every
  Serial.print invisible. `platformio.ini` now sets
  `-D ARDUINO_USB_CDC_ON_BOOT=1`, routing Serial to the USB-C port.
- **The 32 MB flash is OCTAL (OPI) — a quad-SPI build boot-loops.**
  **VERIFIED ON HARDWARE 2026-07-19**, the hard way: a `dio`-mode build flashed
  fine but crash-looped at app startup with `spi_flash: Detected size(512k)
  smaller than the size in the binary image header(32768k)` while the boot ROM
  printed `Octal Flash Mode Enabled` on every reset. The chip's eFuse marks the
  stacked flash as octal, so the app's flash driver must be built for OPI:
  `board_build.arduino.memory_type = opi_opi` (octal flash libs; the second
  `opi` refers to the also-octal 16 MB PSRAM, which stays disabled), with
  `flash_mode = dout` (the standard esptool write mode for OPI parts — DOUT is
  also what the vendor's own test bin stamps, which in hindsight was the tell;
  the XiaoZhi bin's DIO header was a red herring). `flash_size = 32MB`, 80 MHz.
  This is the config that boots. Recovery from the boot-loop was a plain
  reflash — the ROM loader is untouched by any of this. The partition table
  still spans only 8 MB (3 MB per OTA slot is ample at ~1 MB app size); the
  upper 24 MB is simply unused.
- **Serial-over-USB timing quirk:** every reset tears down the USB CDC
  connection, and the host takes ~1–2 s to re-attach — but the boot banner
  prints in the first ~200 ms, so boot-time output is effectively never visible
  on a monitor that was attached across the reset. Steady-state output (frame
  fetch failures, OTA logs) shows fine. Judge first-boot health by the panel
  ("WIFI SETUP" = display + firmware alive), not by catching the banner.
- **Onboard peripherals share no HUB75 pins.** RTC (PCF85063) / IMU (QMI8658) /
  SHTC3 sit on I2C 47/48; audio (ES8311/ES7210) on 43/12/38/21/39/11; TF card on
  17/44/1/14 (MMC-only per the wiki). None collide with the 14 HUB75 GPIOs or
  the octal flash/PSRAM pins (26–37). GPIO 3 (HUB75 C) is a strapping pin
  (JTAG-source select) — benign, but worth knowing.
- **WiFi-under-DMA:** the vendor is silent on the S3 WiFi-vs-DMA EMI question —
  the §4 risk stands unchanged, neither confirmed nor contradicted.

## Assembly & first-boot notes — **VERIFIED ON HARDWARE**

This is the sequence that actually worked. Do steps 1–3 with **nothing plugged in**.

1. **Plug the driver board directly onto the panel.** The board's HUB75 connector is a **female
   socket**; the panel's `IN`/`OUT` headers are **male**. It mates straight on — no ribbon in
   between. Use **`IN`** (the header the panel's silkscreened arrow points *away* from). Match the
   shroud key; it should seat with light, even pressure.
   - The bundled 16-pin gray ribbon is **female on both ends** — it is the *panel-to-panel chaining*
     cable (`OUT` → next panel's `IN`), not a board-to-panel cable. With one panel it is a spare.
2. **Land the panel's VH4 power pigtail on the board's posts.** Unscrew the `5V` and `GND` post
   screws, slip the fork terminals under them, retighten firmly, then tug-test each. **Red → `5V`,
   black → `GND`** (read the silkscreen, don't go by position).
3. **Plug the pigtail's white VH4 connector into the panel's `VCC`/`GND` header.** The pigtail has
   **two** VH4 connectors wired in parallel (for a second panel); either works, and the unused one
   is live 5V — tuck or tape it. Before powering, eyeball that **red lands on `VCC`** per the panel
   silkscreen. Keying guarantees orientation, not that the vendor used the same convention on both
   ends, and reversed polarity destroys the panel.
4. **Power on:** USB-C charger (27W class) → the board's **`POWER`** port. Expect Waveshare's stock
   demo firmware to light the panel. It is likely authored for a **64×64** panel, so a doubled,
   squashed, or half-drawn image on this 64×32 is **normal** and still confirms good wiring. You are
   checking "pixels light," not "picture is correct."
5. **Flash:** USB-C to a computer via the **`USB`** port (not `POWER`). *Unverified* — inferred from
   the silkscreen; if the flash tool can't see the board, swap ports first.
6. First boot opens a WiFi-setup hotspot (WiFiManager); join it, enter home WiFi + the backend
   `frame.bin` URL. It then mirrors the backend's preview.

**Clearance check:** the board rides on the panel's back, cantilevered off the HUB75 connector. The
underside carries the **screw heads of the `5V`/`GND` posts** — live metal. Resting on the panel's
black plastic frame ribs is fine; sitting over the panel's exposed-PCB cutout windows is a short.
Tape over the screw heads if unsure. Dress the pigtail slack away from those windows.

**Safety:** get polarity right at both ends — reversing +/− can kill the board or the panel. Make
all connections with nothing plugged in.
