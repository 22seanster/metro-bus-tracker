# CLAUDE.md

Project context for Claude Code.

## What this is

Metro Bus Tracker — a Tidbyt-style 64×32 HUB75 LED matrix showing Houston METRO
bus arrivals (routes 51/52, stop 3216), plus weather and clock screens. A
Dockerized FastAPI backend (`backend/`) renders every 64×32 frame and serves it
at `/frame.bin`; the ESP32 device (`firmware/`) is a dumb client that fetches the
current frame over WiFi and blits it. New screens never require reflashing the
device. See `README.md` for full setup.

## Hardware

The physical build's bill of materials, the reasoning behind each part, the
alternatives that were rejected, and the firmware changes the chosen board
implies are documented in **`HARDWARE.md`**. Read it before touching `firmware/`
pin config or the PlatformIO board target.

Quick summary: the device is built on a **Waveshare ESP32-S3-RGB-Matrix** driver
board plugged **directly** onto a **64×32 P4** panel, powered by a **27W USB-C
charger** (no barrel jack, no screw terminal, no solder — the board's 5V/GND
copper posts feed the panel's LED power). Hardware assembly is **done and
verified as of 2026-07-18**; only firmware remains. Moving
from the old classic-ESP32 target to this ESP32-S3 board requires a PlatformIO
board change, using the DMA library's **ESP32-S3 default HUB75 pins** (do not
hardcode the old pins) plus the vendor's three deviations — `cfg.gpio.e = 9`,
`cfg.clkphase = false`, and `mxconfig.driver = HUB75_I2S_CFG::SHIFTREG;`
(required for the P4 panel) — and building with USB-CDC serial and DIO/32MB
flash settings (see `platformio.ini` comments). The concrete pin table, init
snippet, and the open WiFi-under-DMA risk (with the `stopDMAoutput()`
mitigation) are in `HARDWARE.md`, including the 2026-07-19 vendor re-check.
The backend and frame protocol are unaffected.
