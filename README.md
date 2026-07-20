# Metro Bus Tracker

A Tidbyt-style 64x32 LED matrix display showing **Houston METRO bus arrivals** for
routes **51 / 52** at stop **3216 (Lorraine St @ Cochran, inbound to Downtown TC)**,
plus rotating **weather** and **clock** screens.

The backend (this repo, Docker) renders every pixel; the ESP32 device is a dumb
client that fetches the current frame over WiFi every few seconds. New screens
(Spotify now-playing is planned) never require reflashing the device.

```
Laptop (Portainer/Docker)                     ESP32 + HUB75 panel
┌───────────────────────────┐                 ┌──────────────────┐
│ METRO GTFS-RT ── bus      │                 │                  │
│ Open-Meteo ──── weather   │── /frame.bin ──▶│ blit 64x32       │
│ clock                     │   (4 KB, ~3 s)  │ RGB565 pixels    │
│   └─▶ renders 64x32 frame │                 │                  │
└───────────────────────────┘                 └──────────────────┘
        └─▶ / (live browser preview + status)
```

## 1. Deploy the backend (Portainer)

1. In Portainer: **Stacks → Add stack → Web editor**, paste `docker-compose.yml`
   from this repo (or use **Repository** pointing at it).
2. Deploy. Open `http://<laptop-ip>:8000/` — you should see the live panel
   preview rotating bus / weather / clock. Bus data is **mock** until you add a key.

### Get your (free) METRO API key

1. Go to <https://api-portal.ridemetro.org/> and **Sign Up**
   (Google or Microsoft account works).
2. Subscribe to the **GTFS Realtime** product; copy your subscription key.
3. In Portainer, edit the stack's env var `METRO_API_KEY`, redeploy.
4. Check `http://<laptop-ip>:8000/status` — `providers.bus.mock` should now be
   `false`, and the arrivals should match the METRO app / T.R.I.P. tracker.

### Configuration (env vars)

| Var | Default | Meaning |
|---|---|---|
| `METRO_API_KEY` | *(empty)* | Empty ⇒ bus screen uses mock data (with a log warning) |
| `MOCK` | `false` | `true` ⇒ mock bus **and** weather (demo mode, no network) |
| `STOP_ID` | `3216` | GTFS stop_id to watch |
| `DIRECTION_ID` | `1` | 1 = inbound to Downtown TC, 0 = outbound |
| `ROUTE_IDS` | `051,052` | GTFS route_ids (zero-padded), comma-separated |
| `ROUTE_LABELS` | *(auto)* | Display labels; default strips leading zeros |
| `ROUTE_COLORS` | `#7B2FBE,#008060` | Badge colors, parallel to `ROUTE_IDS` |
| `BUS_POLL_SECONDS` | `45` | GTFS-RT poll interval |
| `BUS_LOOKAHEAD_MINUTES` | `90` | Arrivals beyond this are ignored; screen drops out of rotation when none |
| `WEATHER_LAT` / `WEATHER_LON` | stop coords | Open-Meteo location |
| `APP_TZ` | `America/Chicago` | Clock + night-window timezone |
| `BUS_DWELL_SECONDS` / `WEATHER_DWELL_SECONDS` / `CLOCK_DWELL_SECONDS` | `12` / `8` / `8` | Rotation dwell per screen |
| `BRIGHTNESS` / `NIGHT_BRIGHTNESS` | `180` / `40` | Panel brightness (0-255), server-controlled |
| `NIGHT_START` / `NIGHT_END` | `22:00` / `06:30` | Night-dimming window (local time) |

Endpoints: `/` preview page · `/frame.png?scale=8` · `/frame.bin` (ESP32) ·
`/firmware.bin` · `/firmware/latest.json` · `/status` · `/healthz`.

## 2. Build the device

### Parts and wiring

See **[`HARDWARE.md`](HARDWARE.md)** for the authoritative bill of materials
and wiring/pin reference — the device is built on a Waveshare
ESP32-S3-RGB-Matrix driver board + a 64x32 P4 panel, no-solder. It also covers
the reasoning behind each part and the alternatives that were rejected.

### Flash the firmware

The default PlatformIO env (`esp32-s3`) targets the S3 board above. A plain
`pio run -t upload` compiles with `FW_BUILD=0`, which makes the device treat
*any* server build as newer and immediately OTA-replace itself — inject the
build number the same way CI does so you can actually test a local change:

```bash
pip install platformio==6.1.19   # matches the version CI builds and flashes with
cd firmware
PLATFORMIO_BUILD_FLAGS="-D FW_BUILD=$(git rev-list --count HEAD) -D FW_SHA='\"'$(git rev-parse --short HEAD)'\"'" pio run -e esp32-s3 -t upload
```

(For the classic-ESP32 fallback board, use `-e esp32dev` instead.)

**If the upload fails to connect to the serial port**, put the board in download
mode by hand — per Waveshare's FAQ: hold **BOOT**, press and release **RESET**,
then release **BOOT**, and retry the upload. This resolves most flashing
problems on this board.

### Troubleshooting the first boot

Watch the serial monitor (`pio device monitor`) on the board's **`USB`** USB-C
port — the board has no USB-UART bridge, so serial output arrives over native
USB CDC (enabled via `ARDUINO_USB_CDC_ON_BOOT` in `platformio.ini`; without it
there is no serial output at all). The firmware prints
`boot: build=<n> sha=<s>` as its first line, so you can always tell which build
a device is actually running.

| Symptom | Likely cause |
|---|---|
| `FATAL: HUB75 DMA memory allocation failed` on serial, panel black | The DMA buffers didn't fit in internal SRAM. WiFi and OTA still run, so a fix can be pushed over the air. |
| Board resets in a loop, USB port keeps re-enumerating | Supply voltage sagging. Waveshare's FAQ: the USB supply must stay **above 4.9 V**. Use the specified 27 W USB-C charger. |
| Display misaligned, torn, or showing garbage | Panel geometry or driver mismatch — check the `SHIFTREG` driver setting, which this P4 panel requires. |
| Panel blank but serial shows frames fetching | Check the 16-pin ribbon seating and the separate panel power lead. |

### First boot

1. The panel shows **WIFI SETUP** and the ESP32 opens an access point
   **BusTracker-Setup**.
2. Join it from your phone; a captive portal opens (or browse to 192.168.4.1).
3. Pick your WiFi network, enter its password, and set
   **Backend frame URL** to `http://<laptop-ip>:8000/frame.bin`.
4. Save — the device reboots and mirrors the browser preview from then on.
   If the backend goes down it shows **NO LINK** and recovers automatically.

## Updating the device (OTA)

Once a device has been flashed once over USB, it never needs a cable again:

1. Push to `main`. CI builds and tests the backend, builds `firmware.bin` for
   the `esp32-s3` env, and bakes both it and `firmware/latest.json` into the
   backend Docker image.
2. Redeploy the stack in Portainer (pull the new image, recreate the
   container).
3. Every device checks `/firmware/latest.json` every 15 minutes (plus once
   ~30s after boot — except the boot immediately following a successful OTA,
   and any boot after a failed attempt, which use the 15-minute delay
   instead; see `setup()`'s `otaFailCount` branch in `firmware/src/main.cpp`)
   and, if the server's `build` number is strictly greater than its own,
   downloads and flashes `/firmware.bin`, then reboots into it.

A failed update (interrupted transfer, out-of-space, etc.) retries at most
**3 times per release**, keyed on the release's `sha` (not its `build`
number, which is a `git rev-list --count` value and can repeat across a
rebase or force-push). After 3 failures the device abandons that specific
sha (logged over serial) so a persistently broken release can't loop the
device forever; publishing a fix — even under the same build number, as long
as the sha differs — is retried fresh. If a device ever does lock itself out,
it's because the abandoned release's sha is still what the backend is
advertising (e.g. `/firmware/latest.json` was never updated to a new sha
after the failure); the only recovery path is a USB reflash — see [Flash the
firmware](#flash-the-firmware) above.

To check what the **backend is serving**, hit `/status` and look at the
`firmware` block (`build`, `sha`, whether a binary is present) — this is the
server's build, not any particular device's. To check what a **device is
running**, connect a serial console (115200 baud) and read the boot line:
`boot: build=<n> sha=<short>`.

## Development

```bash
python -m venv .venv && .venv/Scripts/activate   # or bin/activate
pip install -e "./backend[dev]"
pytest backend/tests
MOCK=true uvicorn app.main:app --reload --app-dir backend   # preview at localhost:8000
```

CI builds and pushes a multi-arch (amd64 + arm64) image to
`ghcr.io/22seanster/metro-bus-tracker:latest` on every push to `main`.

## Spotify now-playing screen (optional)

Shows album art + track/artist whenever you (or another configured account) are
playing Spotify **on a home device**. The screen stays out of the rotation
otherwise.

One-time setup (~10 min):

1. Go to <https://developer.spotify.com/dashboard> → **Create app**.
   Set Redirect URI to exactly `http://127.0.0.1:8765/callback`.
   Note the **Client ID** and **Client Secret** (under app Settings).
2. For a second person: app **Settings → User Management** → add their
   Spotify account email.
3. On your computer, run `python scripts/spotify_auth.py`, paste the client
   id/secret, log in when the browser opens, and copy the printed refresh
   token. Repeat in a **private browser window** for the second account.
4. Set the stack env vars in Portainer and update:

   ```
   SPOTIFY_CLIENT_ID=<client id>
   SPOTIFY_CLIENT_SECRET=<client secret>
   SPOTIFY_REFRESH_TOKENS=sean:<token>,wife:<token>
   SPOTIFY_DEVICE_ALLOWLIST=Kitchen Speaker,Living Room TV
   ```

   `SPOTIFY_REFRESH_TOKENS` order = priority if both accounts are playing.
   `SPOTIFY_DEVICE_ALLOWLIST` is a case-insensitive substring match on the
   playing device's name (see device names in Spotify's device picker);
   leave it empty to show no matter where you're listening. `/status` shows
   what the provider sees.

### Adding a screen

1. New provider in `backend/app/providers/` (subclass `Provider`, implement
   `fetch()`; OAuth token refresh lives inside it).
2. New screen in `backend/app/screens/` implementing the `Screen` protocol
   (`name`, `dwell_seconds`, `is_active()`, `render()`); `is_active` returns
   False when nothing is playing so the rotation skips it.
3. Register both in `build_providers()` / `build_screens()` in
   `backend/app/main.py`, add its env vars to `config.py`. Done — the frame
   protocol and firmware are screen-agnostic.
