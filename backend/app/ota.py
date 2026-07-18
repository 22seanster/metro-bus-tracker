"""Firmware release the backend bundles and serves to devices for OTA.

The compiled ``firmware.bin`` + ``latest.json`` are baked into the image under
``app/firmware/`` by CI. When absent (e.g. a local dev build), the endpoints
report ``present: False`` / 404 and devices simply see "no update".
"""

import json
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent / "firmware"


def firmware_status(firmware_dir: Path = FIRMWARE_DIR) -> dict:
    """Describe the bundled firmware, or a present:False stub if none."""
    meta = firmware_dir / "latest.json"
    binf = firmware_dir / "firmware.bin"
    if not (meta.exists() and binf.exists()):
        return {"present": False, "build": None, "sha": None}
    try:
        data = json.loads(meta.read_text())
        return {"present": True, "build": int(data["build"]), "sha": str(data["sha"])}
    except (ValueError, KeyError, TypeError, OSError):
        # Corrupted/invalid JSON, missing key, bad value, or read error → degrade gracefully
        return {"present": False, "build": None, "sha": None}


def firmware_bin_path(firmware_dir: Path = FIRMWARE_DIR) -> Path | None:
    """Path to the bundled binary, or None if not present."""
    meta = firmware_dir / "latest.json"
    binf = firmware_dir / "firmware.bin"
    return binf if (meta.exists() and binf.exists()) else None
