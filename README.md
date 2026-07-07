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
`/status` · `/healthz`.

## 2. Build the device

### Parts (~$40)

| Part | Notes |
|---|---|
| ESP32 dev board | Classic ESP32-WROOM-32 devkit ("ESP32 DevKitC / NodeMCU-32S", 38-pin) |
| 64x32 RGB LED matrix, HUB75 | P4 (256x128 mm) or P5 (320x160 mm) pitch — pick by case size |
| 5V power supply, ≥4A | Powers the panel (barrel or screw terminals) + ESP32 via 5V/VIN |
| Female-female dupont jumpers | Or an IDC ribbon + breakout for cleaner wiring |
| Wood/3D-printed case + diffuser | LED acrylic or even a paper diffuser mellows the pixels nicely |

### Wiring (HUB75 connector → ESP32)

| HUB75 | ESP32 | HUB75 | ESP32 |
|---|---|---|---|
| R1 | 25 | A | 23 |
| G1 | 26 | B | 19 |
| B1 | 27 | C | 5 |
| R2 | 14 | D | 17 |
| G2 | 12 | E | *(unused on 64x32)* |
| B2 | 13 | LAT | 4 |
| GND | GND | OE | 15 |
| | | CLK | 16 |

Power the panel's 5V input directly from the PSU (not from the ESP32), and
share ground between PSU, panel, and ESP32.

### Flash the firmware

```bash
pip install platformio
cd firmware
pio run -t upload        # ESP32 connected via USB
```

### First boot

1. The panel shows **WIFI SETUP** and the ESP32 opens an access point
   **BusTracker-Setup**.
2. Join it from your phone; a captive portal opens (or browse to 192.168.4.1).
3. Pick your WiFi network, enter its password, and set
   **Backend frame URL** to `http://<laptop-ip>:8000/frame.bin`.
4. Save — the device reboots and mirrors the browser preview from then on.
   If the backend goes down it shows **NO LINK** and recovers automatically.

## Development

```bash
python -m venv .venv && .venv/Scripts/activate   # or bin/activate
pip install -e "./backend[dev]"
pytest backend/tests
MOCK=true uvicorn app.main:app --reload --app-dir backend   # preview at localhost:8000
```

CI builds and pushes a multi-arch (amd64 + arm64) image to
`ghcr.io/22seanster/metro-bus-tracker:latest` on every push to `main`.

### Adding a screen (Phase 2: Spotify now-playing)

1. New provider in `backend/app/providers/` (subclass `Provider`, implement
   `fetch()`; OAuth token refresh lives inside it).
2. New screen in `backend/app/screens/` implementing the `Screen` protocol
   (`name`, `dwell_seconds`, `is_active()`, `render()`); `is_active` returns
   False when nothing is playing so the rotation skips it.
3. Register both in `build_providers()` / `build_screens()` in
   `backend/app/main.py`, add its env vars to `config.py`. Done — the frame
   protocol and firmware are screen-agnostic.
