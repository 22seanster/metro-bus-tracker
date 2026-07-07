"""Bitmap fonts for the 64x32 panel.

BDF sources are bundled; PIL needs its own .pil/.pbm format, so we convert on
first use into a cache directory and memoize the loaded fonts.

  TINY  - tom-thumb, 4px advance x 6px line (3x5 glyphs): dense labels
  SMALL - X11 misc-fixed 5x7: primary text
Big text = render SMALL and integer-upscale.
"""

import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import BdfFontFile, ImageFont

_FONT_DIR = Path(__file__).parent


@lru_cache
def _load(name: str) -> ImageFont.ImageFont:
    cache_dir = Path(tempfile.gettempdir()) / "metro-bus-tracker-fonts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    prefix = cache_dir / name
    if not prefix.with_suffix(".pil").exists():
        with open(_FONT_DIR / f"{name}.bdf", "rb") as f:
            BdfFontFile.BdfFontFile(f).save(str(prefix))
    return ImageFont.load(str(prefix.with_suffix(".pil")))


def tiny() -> ImageFont.ImageFont:
    return _load("tom-thumb")


def small() -> ImageFont.ImageFont:
    return _load("5x7")
