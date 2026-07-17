# ESP32-S3 port + pull-based OTA — Design

_Date: 2026-07-17_

## Goal

Two changes shipped together so the **first USB flash is the last cable
connection** the device ever needs:

1. **Port the firmware** from the old classic-ESP32 target to the actual
   hardware — a Waveshare ESP32-S3-RGB-Matrix board driving a P4 64×32 panel.
2. **Add self-updating OTA** so future firmware changes reach the wall-mounted
   device over WiFi with no cable, no tools, and no being on the same network.

The "dumb client, server is the brain" architecture is preserved and extended:
just as the device pulls the rendered frame from the backend, it now also pulls
its own firmware from the backend.

Non-goals: firmware signing (see Security), a device-side test harness, changes
to the frame protocol or any screen/render logic.

## Background (current state)

- `firmware/platformio.ini` targets `board = esp32dev` (classic ESP32).
- `firmware/include/pins.h` hardcodes the classic-ESP32 HUB75 pin map
  (R1=25, A=23, …) — several of those GPIOs do not physically exist on the S3.
- `firmware/src/main.cpp` builds the panel from that custom pin map and runs a
  simple loop: every 3 s, `GET <frameUrl>`, validate an 8-byte header, blit
  4096 bytes of RGB565. WiFi + backend URL are provisioned via WiFiManager and
  stored in `Preferences`.
- Backend is a Dockerized FastAPI app; CI (`.github/workflows/build.yml`) runs
  tests then builds a multi-arch image from **build context `backend/`** and
  pushes to GHCR on every push to `main`.

The hardware and its firmware follow-ups are documented in `HARDWARE.md`; this
spec implements the follow-ups plus OTA.

## Part 1 — ESP32-S3 port

Per `HARDWARE.md`, three changes, done so **both** the S3 and the classic board
still compile (the classic ESP32 / ESP32-Trinity is the documented fallback if
the S3 has WiFi-under-DMA trouble):

1. **`platformio.ini`** — add an `[env:esp32-s3]` target
   (`board = esp32-s3-devkitc-1`, same `lib_deps`). Keep the existing
   `[env:esp32dev]` env as the fallback board target. The S3 env carries a
   `-D BOARD_S3` build flag.
2. **`initDisplay()`** — under `#ifdef BOARD_S3`, construct the panel with **no
   custom pin map** (`HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1);`) so the DMA
   library uses its built-in ESP32-S3 default pins, and set
   `cfg.driver = HUB75_I2S_CFG::SHIFTREG;` (required for the Waveshare P4 panel).
   The `#else` branch keeps the current classic path using `pins.h`.
3. **`pins.h`** — unchanged; only referenced by the classic build.

Default board target for CI and normal builds is `esp32-s3`.

## Part 2 — Device-side OTA (pull)

A non-blocking check added to the main loop, gated by a timer.

**Cadence:** check **every 15 minutes**, plus one check ~30 s after boot. This
is a single tunable compile-time constant. The check is a few bytes; the device
already fetches a 4 KB frame every 3 s, so this traffic is negligible and can be
lowered (e.g. 5 min) for faster iteration or raised later.

**Check → decide → update:**

1. `GET <host>/firmware/latest.json` → `{"build": <int>, "sha": "<short>"}`.
   `<host>` is **derived from the existing configured frame URL** (same
   scheme/host/port), so no new WiFiManager field is needed.
2. Compare server `build` to the compiled-in `FW_BUILD`. Update **only if the
   server build is strictly greater** — a monotonically increasing integer, so
   deploying an older image can never trigger a downgrade ping-pong.
3. If newer:
   - Show `UPDATING` on the panel (a normal blit).
   - Call **`stopDMAoutput()`** to quiet the panel's RF emissions. The firmware
     download is a ~1 MB transfer — the moment the S3's documented WiFi-vs-DMA
     EMI risk peaks — so we stop DMA for the duration.
   - Run `httpUpdate.update(client, "<host>/firmware.bin")` to stream and flash.
   - On success the device reboots into the new firmware. On failure, log,
     `resumeDMAoutput()`, and resume the normal loop (retry next interval).

**Rollback safety net (critical for a wall-mounted device):** the newly flashed
firmware boots into a *pending* OTA partition and only marks itself permanently
valid after it (a) reconnects WiFi and (b) fetches one frame successfully. If a
bad build panics or can't reach the backend before validating, the bootloader
automatically reverts to the previous firmware on the next reset. A bad OTA
cannot brick the device.

This requires an OTA-capable partition table (two app slots + otadata); set
explicitly via `board_build.partitions` in `platformio.ini`. The app is tiny
relative to the board's 32 MB flash, so a standard dual-OTA scheme is ample.

**Versioning:** `FW_BUILD` is the git commit count (`git rev-list --count HEAD`)
injected at compile time via `-D FW_BUILD=<n>`; `FW_SHA` is the short commit SHA
for humans. Monotonic and cheap to compute in CI.

## Part 3 — Backend endpoints

- `GET /firmware/latest.json` — small JSON `{ "build": <int>, "sha": "<short>" }`
  describing the bundled firmware.
- `GET /firmware.bin` — the firmware binary, served from a path baked into the
  image at build time.
- `/status` gains a `firmware` block (`build`, `sha`, and whether a binary is
  present) for verification, consistent with how arrivals are already exposed
  there.

If no firmware artifact is present in the image (e.g. a local dev build that
skipped the firmware step), the two firmware routes return 404 and `/status`
reports `firmware.present = false`. The device treats a failed/absent check as
"no update" and simply carries on.

## Part 4 — CI pipeline

Extend `.github/workflows/build.yml`:

1. A step (before the Docker build) sets up PlatformIO and runs
   `pio run -e esp32-s3`, passing `-D FW_BUILD=$(git rev-list --count HEAD)` and
   the short SHA.
2. Because the Docker **build context is `backend/`**, the resulting
   `firmware.bin` and a generated `latest.json` are copied into a path **under
   `backend/`** (e.g. `backend/app/firmware/`) so they land in the image via the
   existing Dockerfile copy. The backend serves them from there.
3. The ESP32 binary is architecture-independent, so it is built **once** and
   bundled into both arches of the existing multi-arch (`amd64`+`arm64`) image.

Net flow: `git push main` → CI tests → builds `firmware.bin` → bakes it +
`latest.json` into the backend image → pushes to GHCR → you redeploy the stack
in Portainer → every device self-updates within 15 minutes (or on next boot).

## Part 5 — Security posture

**No firmware signing.** The device pulls from the owner's own LAN backend over
HTTP, exactly as it already pulls unauthenticated frames. The residual risk is a
LAN-present attacker impersonating the backend to push firmware — low stakes for
a kitchen bus clock, and signing adds real complexity (key management, secure
boot / bootloader config). It can be added later without disturbing this design.

## Part 6 — Testing

- **Backend:** unit tests for `/firmware/latest.json`, `/firmware.bin` (present
  and absent cases), and the `/status` firmware block, following existing
  `backend/tests` patterns.
- **Firmware:** no device test harness exists, so validation is manual and also
  serves as the OTA acceptance test:
  1. USB-flash build _N_.
  2. Push a trivial, visibly different change as build _N+1_; let CI publish and
     redeploy the stack.
  3. Confirm the device pulls and switches to _N+1_ **over the air** within the
     check interval — proving OTA works before the enclosure is sealed.

## Risks & open items

- **WiFi-under-DMA EMI on the S3** (from `HARDWARE.md`) — the primary open
  hardware unknown. The OTA download is the worst-case transfer; wrapping it in
  `stopDMAoutput()`/`resumeDMAoutput()` is built into the design. The same
  mitigation can be extended to the per-frame fetch if normal polling proves
  flaky. Last-resort fallback remains the classic-ESP32 / Trinity board, which
  the retained `esp32dev` env still supports.
- **Exact partition scheme** and the exact in-context artifact path are settled
  during implementation planning.
